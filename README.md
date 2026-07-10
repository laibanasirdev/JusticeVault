# ⚖️ JusticeVault — Legal Evidence Integrity Platform

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Solidity](https://img.shields.io/badge/Solidity-0.8-black?style=flat-square&logo=solidity)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red?style=flat-square&logo=streamlit)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=flat-square)

> **Tamper-proof document verification + AI-powered case analysis for legal teams worldwide.**

---

## The Problem

Legal evidence is vulnerable at every step:

- Documents can be altered after submission — silently, undetectably
- Manual review of case files is slow and expensive
- No standardized audit trail exists across most legal workflows
- Courts and law firms have no lightweight way to confirm a file's integrity before acting on it

The result: forged evidence gets processed. Reviewed documents get summarized based on tampered content. Trust breaks down at the worst possible moment.

---

## The Solution

JusticeVault anchors every document to a blockchain with a SHA-256 fingerprint **before** any AI analysis occurs. The system refuses to summarize any file whose hash doesn't match the on-chain record.

**The guarantee:** if a document has been modified even by a single byte after submission, JusticeVault flags it — and stops.

```
Lawyer submits file  →  Hash stored on-chain  →  Oracle verifies integrity
       ↓ mismatch: REJECTED          ↓ match: AI generates Case Brief
                              Judge sees: ✅ On-Chain Integrity Confirmed
```

---

## Key Features

- **Tamper Detection** — SHA-256 fingerprint stored on-chain; any post-submission change triggers an automatic rejection before AI analysis begins
- **AI Case Briefs** — Powered by Claude (Anthropic) via a LangGraph RAG pipeline; extracts Parties, Key Claims, Date of Incident, and Summary from any legal PDF, with guardrails for PII and prompt injection
- **Role-Based Access** — Separate portals for Lawyers (submit), Judges (validate), and Admins (manage) with on-chain access control
- **Full Audit Trail** — Every submission and validation is recorded as a blockchain event; nothing is off-chain or editable
- **IPFS Document Storage** — Files are stored on decentralized infrastructure; no single point of failure or control

---

## Who Is This For?

| User | Use Case |
|------|----------|
| **Law firms** | Verify client-submitted evidence hasn't been altered |
| **Courts & tribunals** | Tamper-proof intake pipeline for digital filings |
| **Legal tech platforms** | Embed integrity verification into existing case management tools |
| **Compliance & eDiscovery teams** | Audit-ready document chains for regulatory submissions |

JusticeVault is jurisdiction-agnostic. It does not depend on any single legal system — the integrity layer works the same whether the court is in the US, EU, or anywhere else.

---

## Tech Stack

| Layer | Technology | Role |
|-------|------------|------|
| **Integrity** | Solidity (Foundry) + Anvil | Evidence registry, role-based access control, on-chain events |
| **Oracle** | Python + Web3.py + LangGraph | Listens for on-chain events, downloads from IPFS, verifies hash, runs the review pipeline |
| **Intelligence** | Claude (Anthropic) + ChromaDB (RAG) | Chunks, embeds, and retrieves document context to generate a structured Case Brief |
| **Storage** | IPFS (via Pinata) | Decentralized, censorship-resistant document storage |
| **UI** | Streamlit | Lawyer, Judge, and Admin dashboards |

---

## Repository Structure

```
contracts/              # Solidity smart contracts (NatSpec documented)
├── JusticeVault.sol    # Evidence registry, roles, events

scripts/
├── monitor_vault.py    # Oracle: listens for events, drives the pipeline
├── oracle_utils.py     # Hash verification, IPFS fetch utilities
├── streamlit_app.py    # Multi-role Streamlit dashboard
├── hash_evidence.py    # CLI tool: compute SHA-256 of a local PDF
└── DeployJusticeVault.s.sol  # Foundry deploy script

pipeline/               # LangGraph oracle pipeline
├── graph.py            # State machine: receive → integrity → embed → analyze → brief → validate
├── guardrails.py        # PII detection + prompt-injection defence
├── rag.py               # Chunk/embed/retrieve (ChromaDB) + Claude brief generation
└── observability.py     # LangSmith tracing config

tests/
├── conftest.py         # Pytest fixtures
├── test_oracle.py      # Pytest: Oracle logic (verify_file_integrity)
├── run_evals.py        # LangSmith eval runner for the RAG pipeline
└── eval_dataset.json   # Sample legal-brief eval cases

.streamlit/             # Streamlit theme config
temp_legal_files/       # Scratch space for local demo PDFs (gitignored)
```

> Note: there are currently no Foundry contract tests (`forge test` will find none) — that's an open gap, not yet implemented.

---

## Quick Start

### Prerequisites

- [Foundry](https://getfoundry.sh/) installed
- Python 3.10+
- A [Pinata](https://pinata.cloud) account for IPFS (uploads are manual via the Pinata dashboard/API — not yet wired into this codebase)
- An [Anthropic API key](https://console.anthropic.com/) (Claude)

### 1. Clone and install

```bash
git clone https://github.com/laibanasirdev/JusticeVault.git
cd JusticeVault
forge install openzeppelin/openzeppelin-contracts
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure environment

Edit `.env` with your values:

```
CONTRACT_ADDRESS=     # filled after deploy step below
ANTHROPIC_API_KEY=    # from console.anthropic.com
PRIVATE_KEY=          # local Anvil account (never use a real funded wallet for dev)
RPC_URL=              # defaults to http://127.0.0.1:8545 (local Anvil)

# Optional — LangSmith tracing for the pipeline
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=
LANGCHAIN_PROJECT=
```

See [`.env.example`](.env.example) for the full template.

> ⚠️ **Never commit your `.env` file.** It is gitignored by default. If you accidentally commit secrets, rotate them immediately and use `git filter-repo` to purge the history.

### 3. Run the local stack

```bash
# Terminal 1 — local blockchain
anvil

# Terminal 2 — deploy contract, copy address to .env
forge script scripts/DeployJusticeVault.s.sol:DeployJusticeVault \
  --rpc-url http://127.0.0.1:8545 --broadcast

# Terminal 3 — start Oracle listener
python scripts/monitor_vault.py

# Terminal 4 — launch UI
streamlit run scripts/streamlit_app.py
```

### 4. Run the demo

```bash
# Get SHA-256 of a PDF
python scripts/hash_evidence.py path/to/document.pdf

# Upload to IPFS via Pinata, then submit via Lawyer portal:
# Case ID + SHA-256 hash + IPFS CID

# Switch to Judge view → see "On-Chain Integrity Confirmed" + Case Brief → Validate
```

---

## Tests

```bash
# Smart contract tests
forge test

# Oracle logic tests
pytest tests/
```

---

## Roadmap

- [ ] REST API layer for integration with existing case management systems
- [ ] Multi-chain support (Polygon, Arbitrum) for lower gas costs
- [ ] Batch evidence submission for high-volume court intake
- [ ] Document redaction detection (flag selectively obscured PDFs)
- [ ] Webhook notifications for legal teams on submission and validation events
- [ ] Enterprise SaaS packaging with tenant isolation

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request so we can discuss the change.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Open a pull request with a clear description

---

## Security

If you find a vulnerability, please **do not open a public issue**. Email the maintainer directly. We take security seriously — especially for a system designed to be trusted by legal professionals.

---

## License

MIT — see [`LICENSE`](LICENSE) for details.

---

## Built By

**Laiba Nasir** — AI & Legal Tech Developer  
[GitHub](https://github.com/laibanasirdev) · [LinkedIn](https://linkedin.com/in/laiba-nasir-187a67267) · [Medium](https://laibanasirdev.medium.com)