import json
import requests
import os
import time
from web3 import Web3
from google import genai
from config import CONTRACT_ADDRESS, ABI_PATH, RPC_URL, GEMINI_API_KEY, IPFS_GATEWAY, TEMP_DIR

# 1. Initialize Clients
w3 = Web3(Web3.HTTPProvider(RPC_URL))
ai_client = genai.Client(api_key=GEMINI_API_KEY)

with open(ABI_PATH) as f:
    abi = json.load(f)["abi"]
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)
def summarize_legal_doc(file_path):
    print(f"🤖 AI is reading the document...")
    max_retries = 3
    retry_delay = 60  # Seconds to wait after a 429 error

    for attempt in range(max_retries):
        try:
            with open(file_path, "rb") as doc_file:
                # We tell the AI: "You are a legal assistant. Summarize this for a judge."
                response = ai_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        "You are an expert legal assistant. Summarize this evidence document into 3 bullet points for a judge.",
                        {"inline_data": {"mime_type": "application/pdf", "data": doc_file.read()}}
                    ]
                )
            return response.text
            
        except Exception as e:
            if "429" in str(e):
                print(f"⏳ Rate limit hit! Attempt {attempt + 1}/{max_retries}. Waiting {retry_delay}s to reset...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Unexpected AI Error: {e}")
                return "Error: Could not process document."

    return "❌ Error: API Quota exhausted after multiple retries."

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
        
        # Trigger AI
        summary = summarize_legal_doc(local_path)
        print(f"⚖️ JUDGE'S SUMMARY:\n{summary}")
        
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