JusticeVault: Decentralized Legal AI Oracle
JusticeVault bridges the gap between decentralized storage and Generative AI. It monitors a Smart Contract for legal evidence filings and automatically generates AI summaries using Google's Gemini 2.0.

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
pip install web3 google-genai requests
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
4. Simulate a Filing
Use cast to grant permissions and submit evidence:

Bash
# Grant Lawyer Role
cast send <CONTRACT_ADDR> "grantRole(bytes32,address)" <ROLE_HASH> <YOUR_ADDR> --private-key <PK> --rpc-url http://127.0.0.1:8545

# Submit Evidence
cast send <CONTRACT_ADDR> "submitEvidence(uint256,bytes32,string)" 101 <HASH> "QmXoyp..." --private-key <PK> --rpc-url http://127.0.0.1:8545
🏗 System Architecture
The system consists of three layers:

The Vault (Solidity): Logic for access control and event emission.

The Monitor (Python): Uses Web3.py to poll logs and manage IPFS downloads.

The Intelligence (Gemini): Processes PDF binary data with a built-in Retry-Logic pattern to handle 429 RESOURCE_EXHAUSTED errors.