import json
import requests
import os
import time
import random
import hashlib
from web3 import Web3
from google import genai
from config import CONTRACT_ADDRESS, ABI_PATH, RPC_URL, GEMINI_API_KEY, IPFS_GATEWAY, TEMP_DIR, FEED_PATH

# 1. Initialize Clients
w3 = Web3(Web3.HTTPProvider(RPC_URL))
ai_client = genai.Client(api_key=GEMINI_API_KEY)

with open(ABI_PATH) as f:
    abi = json.load(f)["abi"]
contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)
def verify_file_integrity(file_path, expected_hash_hex):
    """
    First Principles: Don't trust the IPFS gateway.
    Verify the digital fingerprint.
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read in chunks to handle large legal PDFs efficiently
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        actual_hash = sha256_hash.hexdigest()

        # Normalize expected hash (bytes32 from contract may be HexBytes or bytes)
        if isinstance(expected_hash_hex, bytes):
            clean_expected = expected_hash_hex.hex()
        elif hasattr(expected_hash_hex, "hex"):
            clean_expected = expected_hash_hex.hex()
        else:
            clean_expected = str(expected_hash_hex)
        clean_expected = clean_expected.replace("0x", "").lower()
        actual_hash = actual_hash.lower()

        return actual_hash == clean_expected
    except Exception as e:
        print(f"Error during integrity check: {e}")
        return False


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
                        "You are an expert legal assistant. Summarize this evidence document into 3 bullet points for a judge.",
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
    print("Innovative Laiba AI: Active and Listening...")
    event_filter = contract.events.EvidenceFiled.create_filter(from_block='latest')
    while True:
        for event in event_filter.get_new_entries():
            handle_event(event)

if __name__ == "__main__":
    log_loop()