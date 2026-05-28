import json
import os
import sys
import time
import anthropic
from web3 import Web3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.graph import build_graph, PipelineState
from pipeline.observability import configure_tracing
from oracle_utils import verify_file_integrity
from config import CONTRACT_ADDRESS, ABI_PATH, RPC_URL, ANTHROPIC_API_KEY, FEED_PATH

# ---------------------------------------------------------------------------
# Clients & contract
# ---------------------------------------------------------------------------
configure_tracing()
w3 = Web3(Web3.HTTPProvider(RPC_URL))
ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

with open(ABI_PATH) as f:
    abi = json.load(f)["abi"]
contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

# Compile the LangGraph pipeline once at startup
pipeline_graph = build_graph(ai_client, verify_file_integrity)


# ---------------------------------------------------------------------------
# Feed writer
# ---------------------------------------------------------------------------

def _append_to_feed(state: PipelineState, evidence_index: int) -> None:
    try:
        entry = {
            "caseId":             state["case_id"],
            "index":              evidence_index,
            "status":             state["status"],
            "integrity_verified": state["integrity_verified"],
            "ai_summary":         state["ai_brief"] or state.get("error", ""),
            "pii_flags":          state["pii_flags"],
            "chunk_count":        state["chunk_count"],
            "timestamp_processed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "file_hash_hex":      state["file_hash"].hex() if hasattr(state["file_hash"], "hex") else str(state["file_hash"]),
            "ipfs_cid":           state["ipfs_cid"],
        }
        feed = []
        if os.path.exists(FEED_PATH):
            try:
                with open(FEED_PATH) as f:
                    feed = json.load(f)
            except (json.JSONDecodeError, IOError):
                feed = []
        feed.append(entry)
        with open(FEED_PATH, "w") as f:
            json.dump(feed, f, indent=2)
    except Exception as exc:
        print(f"Warning: could not write feed: {exc}")


def _get_evidence_index(case_id: int) -> int:
    index = 0
    try:
        while True:
            contract.functions.caseRegistry(case_id, index).call()
            index += 1
    except Exception:
        return max(0, index - 1)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def handle_filed_event(event) -> None:
    """EvidenceFiled — run the full pipeline through BRIEF_GENERATED, then pause."""
    case_id = event.args.caseId
    cid     = event.args.ipfsCid
    print(f"\n--- 📂 EvidenceFiled: Case #{case_id} ---")

    initial_state: PipelineState = {
        "case_id":            case_id,
        "ipfs_cid":           cid,
        "file_hash":          event.args.fileHash,
        "local_path":         "",
        "status":             "RECEIVED",
        "integrity_verified": False,
        "pii_flags":          [],
        "injection_detected": False,
        "chunk_count":        0,
        "ai_brief":           "",
        "error":              "",
    }

    thread_cfg = {"configurable": {"thread_id": f"case_{case_id}"}}
    try:
        # Graph runs to BRIEF_GENERATED then pauses (interrupt_before=["validate"])
        result = pipeline_graph.invoke(initial_state, config=thread_cfg)
    except Exception as exc:
        print(f"❌ Pipeline error: {exc}")
        result = {**initial_state, "status": "REJECTED", "error": str(exc)}

    print(f"📝 Writing to feed (status: {result.get('status')})...")
    _append_to_feed(result, _get_evidence_index(case_id))
    print("✨ Feed updated.")


def handle_validated_event(event) -> None:
    """EvidenceValidated — resume the paused graph past the VALIDATE node."""
    case_id = event.args.caseId
    print(f"\n⚖️  EvidenceValidated: Case #{case_id} — resuming pipeline graph...")

    thread_cfg = {"configurable": {"thread_id": f"case_{case_id}"}}
    try:
        result = pipeline_graph.invoke(None, config=thread_cfg)
        print(f"✅ Pipeline complete. Status: {result.get('status')}")
    except Exception as exc:
        print(f"❌ Resume error for case #{case_id}: {exc}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def log_loop() -> None:
    print("🚀 JusticeVault Oracle: Active (LangGraph pipeline mode)...")
    try:
        last_block = 0
        print(f"📊 Listening from block {last_block}")
    except Exception as exc:
        print(f"❌ Connection error — is Anvil running at {RPC_URL}? ({exc})")
        return

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                from_b, to_b = last_block + 1, current_block

                for event in contract.events.EvidenceFiled.get_logs(from_block=from_b, to_block=to_b):
                    print(f"📦 EvidenceFiled in block {event['blockNumber']}")
                    handle_filed_event(event)

                for event in contract.events.EvidenceValidated.get_logs(from_block=from_b, to_block=to_b):
                    print(f"⚖️  EvidenceValidated in block {event['blockNumber']}")
                    handle_validated_event(event)

                last_block = current_block

            time.sleep(2)

        except Exception as exc:
            if "upgrade" in str(exc).lower():
                time.sleep(1)
                continue
            print(f"⚠️  Loop warning: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    log_loop()
