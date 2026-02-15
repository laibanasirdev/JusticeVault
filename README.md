# ⚖️ JusticeVault — Decentralized Legal AI Oracle

**Problem:** Legal evidence is easy to forge, slow to verify, and expensive to analyze. Courts and firms need a way to trust that a document is unchanged and to get instant, structured intelligence without reading every page.

**Solution:** JusticeVault anchors every document to a blockchain with a tamper-proof fingerprint (SHA-256) and uses AI to produce a formal **Case Brief** (Parties, Key Claims, Date of Incident, Summary). The system **never** summarizes a file until its hash matches the on-chain record — so forgery and tampering are detected, not processed.

---

## Why This Matters

| Risk | JusticeVault Response |
|------|------------------------|
| **Evidence tampering** | Document hash is stored on-chain before the AI sees it; the Oracle verifies the downloaded file matches. Mismatch → "Tamper detected," no summary. |
| **Slow verification** | One transaction records the fingerprint; the Oracle + AI deliver a Case Brief automatically. |
| **No audit trail** | Every submission and every judicial validation is on-chain and event-driven. |

**In one sentence:** Lawyers file evidence (hash + IPFS link); the chain stores the fingerprint; an Oracle verifies and asks AI for a Case Brief; Judges see **On-Chain Integrity Confirmed** and validate with one click.

---

## Repository Structure (Client-Ready)

```
contracts/       # Solidity with NatSpec — access control, evidence registry, events
scripts/          # Oracle (monitor_vault.py, oracle_utils.py) | UI (streamlit_app.py) | deploy & hash tool
test/            # Foundry unit tests for JusticeVault
tests/           # Pytest for Oracle logic (e.g. verify_file_integrity)
docs/            # System architecture diagram (ARCHITECTURE.md)
sample_evidence/ # Place 2–3 demo PDFs here; use hash_evidence.py to get SHA-256
```

---

## Quick Start

1. **Clone and install**
   ```bash
   git clone https://github.com/your-username/JusticeVault.git && cd JusticeVault
   forge install openzeppelin/openzeppelin-contracts
   pip install -r requirements.txt
   cp .env.example .env   # Set CONTRACT_ADDRESS, GEMINI_API_KEY, PRIVATE_KEY
   ```

2. **Run the stack**
   - Terminal 1: `anvil`
   - Terminal 2: `forge script scripts/DeployJusticeVault.s.sol:DeployJusticeVault --rpc-url http://127.0.0.1:8545 --broadcast` → put deployed address in `.env`
   - Terminal 3: `python scripts/monitor_vault.py` (Oracle)
   - Terminal 4: `streamlit run scripts/streamlit_app.py` (Dashboard)

3. **Demo with real PDFs**
   - Add PDFs to `sample_evidence/`; run `python scripts/hash_evidence.py sample_evidence/yourfile.pdf`
   - Upload the PDF to IPFS (e.g. Pinata), then submit via Lawyer portal (case ID + hash + CID)
   - In Judge view, see **On-Chain Integrity Confirmed** and the Case Brief; click Validate

📖 **Full usage, role hashes, and troubleshooting:** [USAGE.md](USAGE.md)  
🏗 **System diagram and data flow:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Tests (Reliability)

- **Contract:** `forge test` (Foundry tests in `test/JusticeVault.t.sol`)
- **Oracle logic:** `pytest tests/` (e.g. `verify_file_integrity` in `tests/test_oracle.py`)

---

## Tech Stack

| Layer | Role |
|-------|------|
| **Integrity** | Solidity (Foundry), Anvil — evidence registry, roles, events |
| **Logic** | Python, Web3.py — event listener, IPFS download, hash check |
| **Intelligence** | Google Gemini 2.0 — formal Case Brief (Parties, Key Claims, Date, Summary) |
| **Storage** | IPFS — decentralized document storage |

---

## License

MIT
