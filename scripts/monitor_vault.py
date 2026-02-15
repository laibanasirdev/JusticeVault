import json
import os
import random
import time
import requests
from web3 import Web3
from google import genai

from config import CONTRACT_ADDRESS, ABI_PATH, RPC_URL, GEMINI_API_KEY, IPFS_GATEWAY, TEMP_DIR, FEED_PATH
from oracle_utils import verify_file_integrity

# 1. Initialize Clients
w3 = Web3(Web3.HTTPProvider(RPC_URL))
ai_client = genai.Client(api_key=GEMINI_API_KEY)

with open(ABI_PATH) as f:
    abi = json.load(f)["abi"]
contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)


def summarize_legal_doc(file_path):
    print(f"🤖 AI is reading the document...")
    attempts = 0
    max_attempts = 5

    while attempts < max_attempts:
        try:
            with open(file_path, "rb") as doc_file:
                response = ai_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        "You are an expert legal assistant. Produce a formal Judicial Case Brief from this evidence document. "
"Use this exact structure with bold section labels: **Parties Involved:** (names/roles); **Key Claims:** (main factual or legal claims); **Date of Incident / Relevance:** (dates and why they matter); **Summary:** (2–3 bullet points for the judge).",
                        {"inline_data": {"mime_type": "application/pdf", "data": doc_file.read()}}
                    ]
                )
            return response.text

        except Exception as e:
            if "429" in str(e):  # Rate limit hit
                attempts += 1
                # Exponential backoff: 2, 4, 8, 16, 32 seconds + jitter
                wait_time = (2 ** attempts) + random.random()
                print(f"⏳ Rate limit hit. Attempt {attempts}/{max_attempts}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                print(f"❌ Unexpected AI Error: {e}")
                raise e

    return "❌ Error: Maximum AI retry attempts reached."


def _append_to_feed(case_id, index, integrity_verified, ai_summary, file_hash_hex, ipfs_cid):
    """Write oracle result to evidence feed for the dashboard."""
    try:
        file_hash_str = file_hash_hex.hex() if hasattr(file_hash_hex, "hex") else str(file_hash_hex)
        entry = {
            "caseId": case_id,
            "index": index,
            "integrity_verified": integrity_verified,
            "ai_summary": ai_summary,
            "timestamp_processed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "file_hash_hex": file_hash_str,
            "ipfs_cid": ipfs_cid,
        }
        feed = []
        if os.path.exists(FEED_PATH):
            try:
                with open(FEED_PATH, "r") as f:
                    feed = json.load(f)
            except (json.JSONDecodeError, IOError):
                feed = []
        feed.append(entry)
        with open(FEED_PATH, "w") as f:
            json.dump(feed, f, indent=2)
    except Exception as e:
        print(f"Warning: could not write feed: {e}")


def handle_event(event):
    case_id = event.args.caseId
    cid = event.args.ipfsCid
    print(f"\n--- 📂 New Evidence: Case #{case_id} ---")
    
    # Download from IPFS
    file_url = f"{IPFS_GATEWAY}{cid}"
    local_path = os.path.join(TEMP_DIR, f"case_{case_id}_{cid[:6]}.pdf")
    
    try:
        response = requests.get(file_url, timeout=10)
        with open(local_path, "wb") as f:
            f.write(response.content)

        # Zero Trust: verify file matches on-chain fingerprint before processing
        if verify_file_integrity(local_path, event.args.fileHash):
            print("✅ Integrity Verified: Document matches Blockchain Fingerprint.")
            summary = summarize_legal_doc(local_path)
            print(f"⚖️ JUDGE'S SUMMARY:\n{summary}")
            ai_summary = summary
            integrity_verified = True
        else:
            print("❌ ALERT: TAMPER DETECTED! IPFS file does not match Blockchain hash.")
            ai_summary = "Not available — tamper detected."
            integrity_verified = False

        # Evidence index: getter is caseRegistry(caseId, index) — loop until out of range
        index = 0
        while True:
            try:
                contract.functions.caseRegistry(case_id, index).call()
                index += 1
            except Exception:
                break
        index = index - 1  # last valid index is the evidence we just processed
        _append_to_feed(
            case_id, index, integrity_verified, ai_summary,
            event.args.fileHash, cid,
        )

    except Exception as e:
        print(f"❌ Error processing document: {e}")

def log_loop():
    print("🚀 JusticeVault Oracle: Active and Listening (Stateless Mode)...")
    
    # We start from the latest block when the script begins
    last_processed_block = w3.eth.block_number

    while True:
        try:
            # Current tip of the chain
            current_block = w3.eth.block_number

            if last_processed_block < current_block:
                # Manually fetch logs between the last block we saw and now
                # This replaces the 'create_filter' logic
                new_entries = contract.events.EvidenceFiled.get_logs(
                    fromBlock=last_processed_block + 1,
                    toBlock=current_block
                )

                for event in new_entries:
                    handle_event(event)
                
                # Update our bookmark so we don't process the same logs twice
                last_processed_block = current_block

            # Give the CPU a breath (1-2 seconds is standard for local dev)
            time.sleep(2)

        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    log_loop()