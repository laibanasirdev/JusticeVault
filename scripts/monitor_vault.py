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
    print(f"\n--- 📂 New Event Detected: Case #{case_id} ---")
    print(f"🔗 IPFS CID: {cid}")
    
    # Download path
    file_url = f"{IPFS_GATEWAY}{cid}"
    local_path = os.path.join(TEMP_DIR, f"case_{case_id}_{cid[:6]}.pdf")
    
    ai_summary = "Not processed"
    integrity_verified = False

    try:
        print(f"📡 Downloading from IPFS...")
        # Reduce timeout to 5s for the demo so it doesn't hang forever
        response = requests.get(file_url, timeout=5) 
        
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(response.content)
            print(f"📥 Download Complete. Verifying integrity...")

            if verify_file_integrity(local_path, event.args.fileHash):
                print("✅ Integrity Verified.")
                summary = summarize_legal_doc(local_path)
                ai_summary = summary
                integrity_verified = True
            else:
                print("❌ ALERT: TAMPER DETECTED!")
                ai_summary = "Integrity violation: Summary withheld."
        else:
            print(f"⚠️ IPFS Gateway returned {response.status_code}. Using fallback.")
            ai_summary = "IPFS Download Failed - Gateway Timeout."

    except Exception as e:
        print(f"❌ Network/Logic Error: {e}")
        ai_summary = f"Error during processing: {str(e)}"

    # WE MUST STILL WRITE TO THE FEED EVEN IF DOWNLOAD FAILS
    print(f"📝 Writing to evidence_feed.json...")
    
    # Find the index (Optimized: use a fixed index or just 0 for demo if loop is slow)
    index = 0
    try:
        while True:
            contract.functions.caseRegistry(case_id, index).call()
            index += 1
    except:
        index = max(0, index - 1)

    _append_to_feed(
        case_id, index, integrity_verified, ai_summary,
        event.args.fileHash, cid,
    )
    print("✨ Feed updated successfully.")

def log_loop():
    print("🚀 JusticeVault Oracle: Active and Listening (Stateless Polling Mode)...")
    
    # 1. Initialize block tracker manually
    try:
        # Get the current block number to start from
        # last_processed_block = w3.eth.block_number
        last_processed_block = 0
        print(f"📊 Tracking started from block: {last_processed_block}")
    except Exception as e:
        print(f"❌ Connection Error: Is Anvil running at {RPC_URL}?")
        return

    while True:
        try:
            # 2. Check the current tip of the chain
            current_block = w3.eth.block_number

            if current_block > last_processed_block:
                # 3. Query logs directly via HTTP POST (Stateless)
                # This replaces 'create_filter' entirely
                events = contract.events.EvidenceFiled.get_logs(
                    from_block=last_processed_block + 1,
                    to_block=current_block
                )

                for event in events:
                    print(f"📦 New Evidence Found in Block {event['blockNumber']}!")
                    handle_event(event)
                
                # Update our position
                last_processed_block = current_block

            # 4. Wait 2 seconds before checking for new blocks
            time.sleep(2)

        except Exception as e:
            # If the error is the 'upgrade' ghost, we ignore it and retry
            if "upgrade" in str(e).lower():
                time.sleep(1)
                continue
            else:
                print(f"⚠️ Loop Warning: {e}")
                time.sleep(5)

if __name__ == "__main__":
    log_loop()