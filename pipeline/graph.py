"""
LangGraph oracle pipeline for JusticeVault.

States:  RECEIVED → INTEGRITY_CHECK → EMBEDDING → ANALYSIS → BRIEF_GENERATED
                                                                      ↓ (interrupt)
                                                                  VALIDATED
Any node failure → REJECTED

Human-in-the-loop: graph interrupts before the VALIDATE node.
The oracle resumes when it detects an EvidenceValidated event on-chain.
"""
import os
import sys
import requests
from typing import TypedDict, Literal

import anthropic
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.guardrails import scan_document
from pipeline.rag import ingest_document, generate_brief

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMP_DIR = os.path.join(_BASE_DIR, "temp_legal_files")
_IPFS_GATEWAY = os.getenv("IPFS_GATEWAY", "https://ipfs.io/ipfs/")

Status = Literal[
    "RECEIVED", "INTEGRITY_CHECK", "EMBEDDING",
    "ANALYSIS", "BRIEF_GENERATED", "VALIDATED", "REJECTED",
]


class PipelineState(TypedDict):
    case_id: int
    ipfs_cid: str
    file_hash: bytes
    local_path: str
    status: Status
    integrity_verified: bool
    pii_flags: list[str]
    injection_detected: bool
    chunk_count: int
    ai_brief: str
    error: str


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def _receive(state: PipelineState) -> dict:
    case_id, cid = state["case_id"], state["ipfs_cid"]
    local_path = os.path.join(_TEMP_DIR, f"case_{case_id}_{cid[:6]}.pdf")
    os.makedirs(_TEMP_DIR, exist_ok=True)
    print(f"📡 [RECEIVED] Downloading case #{case_id} from IPFS...")
    try:
        resp = requests.get(f"{_IPFS_GATEWAY}{cid}", timeout=10)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
        print(f"📥 Download complete.")
        return {"local_path": local_path, "status": "INTEGRITY_CHECK"}
    except Exception as exc:
        return {"status": "REJECTED", "error": f"Download failed: {exc}"}


def _integrity_check(state: PipelineState, verify_fn) -> dict:
    print(f"🔐 [INTEGRITY_CHECK] Verifying SHA-256 for case #{state['case_id']}...")
    try:
        if verify_fn(state["local_path"], state["file_hash"]):
            print("✅ Integrity verified.")
            return {"integrity_verified": True, "status": "EMBEDDING"}
        print("❌ TAMPER DETECTED.")
        return {"integrity_verified": False, "status": "REJECTED",
                "error": "File hash mismatch — tamper detected"}
    except Exception as exc:
        return {"status": "REJECTED", "error": f"Integrity check failed: {exc}"}


def _embedding(state: PipelineState) -> dict:
    print(f"🛡️  [EMBEDDING] Guardrails + ingest for case #{state['case_id']}...")
    try:
        scan = scan_document(state["local_path"])
        print(f"   Guardrails: {scan.summary()}")
        if not scan.safe:
            print("🚨 Prompt injection detected — blocking LLM.")
            return {
                "status": "REJECTED",
                "injection_detected": True,
                "pii_flags": scan.pii_detections,
                "error": f"Prompt injection: {scan.summary()}",
            }
        if scan.pii_detections:
            print(f"⚠️  PII flagged: {', '.join(scan.pii_detections)}")
        count = ingest_document(state["local_path"], state["case_id"])
        return {
            "status": "ANALYSIS",
            "injection_detected": False,
            "pii_flags": scan.pii_detections,
            "chunk_count": count,
        }
    except Exception as exc:
        return {"status": "REJECTED", "error": f"Embedding failed: {exc}"}


def _analysis(state: PipelineState, ai_client: anthropic.Anthropic) -> dict:
    print(f"🤖 [ANALYSIS] Generating brief for case #{state['case_id']}...")
    try:
        brief = generate_brief(state["case_id"], ai_client)
        return {"status": "BRIEF_GENERATED", "ai_brief": brief}
    except Exception as exc:
        return {"status": "REJECTED", "error": f"Brief generation failed: {exc}"}


def _brief_generated(state: PipelineState) -> dict:
    # Graph interrupts here — judge validates on-chain, oracle resumes graph
    print(f"📋 [BRIEF_GENERATED] Case #{state['case_id']} ready. Awaiting judicial validation.")
    return {}


def _validate(state: PipelineState) -> dict:
    # Resumed after judge calls validateEvidence() on-chain
    print(f"⚖️  [VALIDATED] Case #{state['case_id']} judicially confirmed.")
    return {"status": "VALIDATED"}


def _rejected(state: PipelineState) -> dict:
    print(f"🚫 [REJECTED] Case #{state['case_id']}: {state.get('error', 'unknown error')}")
    return {}


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------

def _after_receive(state: PipelineState) -> str:
    return "integrity_check" if state["status"] == "INTEGRITY_CHECK" else "rejected"

def _after_integrity(state: PipelineState) -> str:
    return "embedding" if state["status"] == "EMBEDDING" else "rejected"

def _after_embedding(state: PipelineState) -> str:
    return "analysis" if state["status"] == "ANALYSIS" else "rejected"

def _after_analysis(state: PipelineState) -> str:
    return "brief_generated" if state["status"] == "BRIEF_GENERATED" else "rejected"


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_graph(ai_client: anthropic.Anthropic, verify_fn) -> StateGraph:
    """
    Compile the oracle pipeline graph.
    Pass ai_client and verify_fn so nodes can close over them without globals.
    """
    def integrity_check(state): return _integrity_check(state, verify_fn)
    def analysis(state):        return _analysis(state, ai_client)

    builder = StateGraph(PipelineState)

    builder.add_node("receive",         _receive)
    builder.add_node("integrity_check", integrity_check)
    builder.add_node("embedding",       _embedding)
    builder.add_node("analysis",        analysis)
    builder.add_node("brief_generated", _brief_generated)
    builder.add_node("validate",        _validate)
    builder.add_node("rejected",        _rejected)

    builder.set_entry_point("receive")

    builder.add_conditional_edges("receive",         _after_receive,   {"integrity_check": "integrity_check", "rejected": "rejected"})
    builder.add_conditional_edges("integrity_check", _after_integrity,  {"embedding": "embedding",             "rejected": "rejected"})
    builder.add_conditional_edges("embedding",       _after_embedding,  {"analysis": "analysis",               "rejected": "rejected"})
    builder.add_conditional_edges("analysis",        _after_analysis,   {"brief_generated": "brief_generated", "rejected": "rejected"})

    builder.add_edge("brief_generated", "validate")
    builder.add_edge("validate",        END)
    builder.add_edge("rejected",        END)

    checkpointer = MemorySaver()
    # Graph pauses before validate — resumes when judge validates on-chain
    return builder.compile(checkpointer=checkpointer, interrupt_before=["validate"])
