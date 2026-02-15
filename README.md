JusticeVault: Decentralized Legal AI Oracle
JusticeVault bridges the gap between decentralized storage and Generative AI. It monitors a Smart Contract for legal evidence filings and automatically generates AI summaries using Google's Gemini 2.0.

📖 **Full usage guide & project details:** see [USAGE.md](USAGE.md) for step-by-step setup, configuration, role hashes, hashing PDFs, and troubleshooting.

🛠 Prerequisites
Foundry (Forge & Cast)

Python 3.10+

A Gemini API Key

📥 Installation
Clone the repository:

Bash
git clone https://github.com/your-username/JusticeVault.git
cd JusticeVault
Install Smart Contract Dependencies:

Bash
forge install openzeppelin/openzeppelin-contracts
Install Python Requirements:

Bash
pip install -r requirements.txt
# Or: pip install web3 google-genai requests python-dotenv streamlit

🚀 Execution Guide
1. Start Local Blockchain
In a dedicated terminal:

Bash
anvil
2. Deploy the Contract
In a new terminal:

Bash
forge script script/DeployJusticeVault.s.sol:DeployJusticeVault --rpc-url http://127.0.0.1:8545 --broadcast
Note: Copy the Deployed to: address into scripts/config.py.

3. Start the AI Listener
Bash
export GEMINI_API_KEY='your_key_here'
python3 scripts/monitor_vault.py
4. (Optional) Start the Dashboard
Run the Streamlit dashboard for Lawyer / Judge / Admin views (role switcher, evidence feed, validate button):

Bash
streamlit run scripts/streamlit_app.py
Set CONTRACT_ADDRESS in .env. For signing txs from the app, set PRIVATE_KEY (or LAWYER_PRIVATE_KEY, JUDGE_PRIVATE_KEY, ADMIN_PRIVATE_KEY) in .env.

5. Simulate a Filing
Use cast to grant permissions and submit evidence:

Bash
# Grant Lawyer Role
cast send <CONTRACT_ADDR> "grantRole(bytes32,address)" <ROLE_HASH> <YOUR_ADDR> --private-key <PK> --rpc-url http://127.0.0.1:8545

# Submit Evidence
cast send <CONTRACT_ADDR> "submitEvidence(uint256,bytes32,string)" 101 <HASH> "QmXoyp..." --private-key <PK> --rpc-url http://127.0.0.1:8545

6. Judge Validates Evidence (Human-in-the-Loop)
After the AI summary is generated, a Judge can officially validate the evidence on-chain:

Bash
# Grant Judge Role (as admin)
cast send <CONTRACT_ADDR> "grantRole(bytes32,address)" $(cast keccak "JUDGE_ROLE") <JUDGE_ADDR> --private-key <ADMIN_PK> --rpc-url http://127.0.0.1:8545

# Judge validates the first piece of evidence for Case 101 (index 0)
cast send <CONTRACT_ADDR> "validateEvidence(uint256,uint256)" 101 0 --private-key <JUDGE_PRIVATE_KEY> --rpc-url http://127.0.0.1:8545

🏗 System Architecture
The system consists of three layers:

The Vault (Solidity): Logic for access control and event emission.

The Monitor (Python): Uses Web3.py to poll logs and manage IPFS downloads.

The Intelligence (Gemini): Processes PDF binary data with a built-in Retry-Logic pattern to handle 429 RESOURCE_EXHAUSTED errors.

🔄 The Legal Loop (End-to-End)
1. **Lawyer:** Uploads PDF to IPFS → gets CID. Calls `submitEvidence(caseId, hash, cid)`. Contract emits `EvidenceFiled`.
2. **Python Oracle:** Listens for the event → downloads from IPFS → verifies hash (Zero Trust) → summarizes via Gemini (exponential backoff).
3. **Judge:** Reads the AI summary in their dashboard.
4. **Judge:** Calls `validateEvidence(caseId, index)`. Evidence is permanently marked validated on-chain; `EvidenceValidated` event is emitted.