"""
JusticeVault Dashboard — User-first frontend for Lawyer, Judge, and Admin.
Run from project root: streamlit run scripts/streamlit_app.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from web3 import Web3

# Ensure we can import config (run from project root)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    ABI_PATH,
    BASE_DIR,
    CONTRACT_ADDRESS,
    FEED_PATH,
    IPFS_GATEWAY,
    RPC_URL,
)

# --- Page config & layout ---
st.set_page_config(page_title="JusticeVault", page_icon="⚖️", layout="wide")

# Legal Blue accent for key elements (badges, borders)
st.markdown("""
<style>
    .integrity-badge { padding: 0.5rem 0.75rem; border-radius: 0.5rem; background: #0d5c2e; color: white; font-weight: 600; }
    .tamper-badge { padding: 0.5rem 0.75rem; border-radius: 0.5rem; background: #8b1a1a; color: white; font-weight: 600; }
    .case-brief-box { background: #1A1D24; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #1E3A5F; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)
st.title("⚖️ JusticeVault — Decentralized Legal AI Oracle")

# --- Web3 setup ---
@st.cache_resource
def get_contract():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        return None, None
    with open(ABI_PATH) as f:
        abi = json.load(f)["abi"]
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)
    return w3, contract


def get_chain_label():
    try:
        w3, _ = get_contract()
        if w3 and w3.is_connected():
            chain_id = w3.eth.chain_id
            if chain_id == 31337:
                return "Anvil (local)"
            if chain_id == 8453:
                return "Base"
            return f"Chain ID {chain_id}"
    except Exception:
        pass
    return "Disconnected"


def load_feed():
    if not os.path.exists(FEED_PATH):
        return []
    try:
        with open(FEED_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def get_evidence_list(contract, case_id):
    """Get all evidence for a case. ABI getter is caseRegistry(caseId, index) — two args."""
    evidence_list = []
    idx = 0
    while True:
        try:
            ev = contract.functions.caseRegistry(case_id, idx).call()
            evidence_list.append(ev)
            idx += 1
        except Exception:
            break
    return evidence_list


def feed_entry(case_id, index):
    """Get latest feed entry for (caseId, index)."""
    feed = load_feed()
    for e in reversed(feed):
        if e.get("caseId") == case_id and e.get("index") == index:
            return e
    return None


# --- Role switcher ---
role = st.selectbox(
    "**View dashboard as:**",
    ["Lawyer", "Judge", "Admin"],
    index=1,
)

# --- Global Truth (Header) ---
chain = get_chain_label()
if chain.startswith("Anvil") or "Disconnected" in chain:
    st.caption(f"🌐 Network: **{chain}**")
else:
    st.caption(f"🌐 Network: **{chain}** (Ethereum L2)")

# --- Lawyer Portal ---
if role == "Lawyer":
    st.header("📤 Lawyer Portal: Submit New Evidence")
    st.caption("Upload progress: prepare your document hash and IPFS CID, then submit on-chain.")

    with st.form("submit_evidence"):
        case_id = st.number_input("Case ID", min_value=1, value=101, step=1)
        hash_hex = st.text_input(
            "Document SHA-256 hash (64 hex characters)",
            placeholder="e.g. 1234567890abcdef...",
            help="Compute with: sha256sum yourfile.pdf",
        )
        ipfs_cid = st.text_input(
            "IPFS CID (after uploading your PDF to IPFS)",
            placeholder="e.g. QmXoyp...",
        )
        submitted = st.form_submit_button("Submit Evidence")

    if submitted:
        pk = os.getenv("LAWYER_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
        if not pk or not hash_hex.strip() or not ipfs_cid.strip():
            st.error("Set LAWYER_PRIVATE_KEY (or PRIVATE_KEY) in .env and fill Hash + IPFS CID.")
        else:
            try:
                w3, contract = get_contract()
                if not w3 or not w3.is_connected():
                    st.error("Cannot connect to chain. Is Anvil running?")
                else:
                    # Normalize hash to bytes32 (64 hex chars, with 0x for cast-style)
                    h = hash_hex.strip().replace("0x", "")
                    if len(h) != 64 or not all(c in "0123456789abcdefABCDEF" for c in h):
                        st.error("Hash must be 64 hexadecimal characters.")
                    else:
                        account = w3.eth.account.from_key(pk.strip())
                        tx = contract.functions.submitEvidence(
                            case_id,
                            bytes.fromhex(h),
                            ipfs_cid.strip(),
                        ).build_transaction(
                            {"from": account.address, "gas": 300_000, "chainId": w3.eth.chain_id}
                        )
                        signed = w3.eth.account.sign_transaction(
                            tx, private_key=account.key
                        )
                        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                        st.success(
                            f"✅ **Submission confirmed.** "
                            f"Tx: `{tx_hash.hex()}` — Oracle will process and summarize shortly."
                        )
                        st.balloons()
            except Exception as e:
                st.error(f"Transaction failed: {e}")

# --- Judge Portal ---
elif role == "Judge":
    st.header("🏛 Judicial Portal: Review Pending Evidence")
    st.caption("Evidence feed with integrity status and AI brief. Validate after review.")

    # Case selector
    case_id_input = st.number_input(
        "Case ID to review",
        min_value=1,
        value=101,
        step=1,
        key="judge_case_id",
    )
    st.caption(f"**Viewing Case #** {case_id_input}")
    w3, contract = get_contract()

    if not w3 or not w3.is_connected():
        st.warning("Connect to chain (e.g. start Anvil) to load evidence.")
    else:
        with st.status("Loading evidence from chain...", expanded=False) as status:
            evidence_list = get_evidence_list(contract, case_id_input)
            status.update(label="Evidence loaded", state="complete")

        if not evidence_list:
            st.info(f"No evidence on-chain for Case #{case_id_input} yet.")
        else:
            st.subheader("Evidence History")
            st.caption(f"All evidence filed for Case #{case_id_input} — review and validate below.")
            feed = load_feed()

            for idx, ev in enumerate(evidence_list):
                case_id, file_hash, ipfs_cid, lawyer, timestamp, isValidated = ev
                ts = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M UTC")
                hash_hex = file_hash.hex() if hasattr(file_hash, "hex") else str(file_hash)
                hash_short = hash_hex[:16] + "…" if len(hash_hex) > 16 else hash_hex

                entry = feed_entry(case_id_input, idx)
                integrity_verified = entry.get("integrity_verified") if entry else None
                ai_summary = entry.get("ai_summary") if entry else None

                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"**Evidence #{idx}** · {ts}")
                        st.caption(f"Hash: `{hash_short}` · Lawyer: `{lawyer[:10]}…`")
                    with col2:
                        if integrity_verified is True:
                            st.markdown('<span class="integrity-badge">✅ On-Chain Integrity Confirmed</span>', unsafe_allow_html=True)
                            st.caption("Document hash matches blockchain fingerprint.")
                        elif integrity_verified is False:
                            st.markdown('<span class="tamper-badge">⚠️ Tamper detected</span>', unsafe_allow_html=True)
                            st.caption("Hash mismatch — do not rely on this file.")
                        else:
                            st.caption("⏳ Pending Oracle — waiting for AI analysis.")
                    with col3:
                        if isValidated:
                            st.success("Validated ✓")
                        else:
                            st.caption("Not validated")

                    # Case Brief card (highlight style)
                    if ai_summary:
                        st.markdown("**Case Brief**")
                        st.markdown(f"<div class='case-brief-box'>{ai_summary.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
                    else:
                        st.caption("_No Case Brief yet (Oracle may still be processing)._")

                    # Validate button (only if not already validated)
                    if not isValidated:
                        if st.button(f"Validate evidence #{idx}", key=f"validate_{case_id_input}_{idx}"):
                            judge_pk = os.getenv("JUDGE_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
                            if not judge_pk:
                                st.error("Set JUDGE_PRIVATE_KEY (or PRIVATE_KEY) in .env.")
                            else:
                                try:
                                    account = w3.eth.account.from_key(judge_pk.strip())
                                    tx = contract.functions.validateEvidence(
                                        case_id_input, idx
                                    ).build_transaction(
                                        {"from": account.address, "gas": 150_000, "chainId": w3.eth.chain_id}
                                    )
                                    signed = w3.eth.account.sign_transaction(tx, private_key=account.key)
                                    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                                    w3.eth.wait_for_transaction_receipt(tx_hash)
                                    st.success(f"Evidence #{idx} validated. Tx: `{tx_hash.hex()}`")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Validation failed: {e} (Do you have JUDGE_ROLE?)")

                    st.divider()

            # Audit trail (bottom)
            st.subheader("Audit Trail")
            st.caption("On-chain custody: evidence is stored in the JusticeVault contract.")
            if chain_id := (w3.eth.chain_id if w3 else None):
                if chain_id == 31337:
                    st.info("Local Anvil — no block explorer. Chain of custody is in the contract state.")
                else:
                    st.markdown(f"Contract: `{CONTRACT_ADDRESS}` (view on block explorer for chain ID {chain_id})")

# --- Admin Portal ---
else:
    st.header("🔐 Admin Portal: Manage Roles")
    st.caption("Grant or revoke Lawyer and Judge roles. Requires DEFAULT_ADMIN_ROLE.")

    w3, contract = get_contract()
    role_hashes = {
        "Lawyer": Web3.keccak(text="LAWYER_ROLE"),
        "Judge": Web3.keccak(text="JUDGE_ROLE"),
    }

    with st.form("admin_roles"):
        target_address = st.text_input("Address to manage", placeholder="0x...")
        role_choice = st.selectbox("Role", ["Lawyer", "Judge"])
        col1, col2 = st.columns(2)
        with col1:
            grant = st.form_submit_button("Grant role")
        with col2:
            revoke = st.form_submit_button("Revoke role")

    if grant or revoke:
        admin_pk = os.getenv("ADMIN_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
        if not admin_pk or not target_address or not target_address.strip().startswith("0x"):
            st.error("Set ADMIN_PRIVATE_KEY (or PRIVATE_KEY) and enter a valid address.")
        else:
            try:
                account = w3.eth.account.from_key(admin_pk.strip())
                role_hash = role_hashes[role_choice]
                addr = Web3.to_checksum_address(target_address.strip())
                if grant:
                    tx = contract.functions.grantRole(role_hash, addr).build_transaction(
                        {"from": account.address, "gas": 100_000, "chainId": w3.eth.chain_id}
                    )
                    signed = w3.eth.account.sign_transaction(tx, private_key=account.key)
                    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                    w3.eth.wait_for_transaction_receipt(tx_hash)
                    st.success(f"Granted **{role_choice}** to `{addr}`.")
                else:
                    tx = contract.functions.revokeRole(role_hash, addr).build_transaction(
                        {"from": account.address, "gas": 100_000, "chainId": w3.eth.chain_id}
                    )
                    signed = w3.eth.account.sign_transaction(tx, private_key=account.key)
                    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                    w3.eth.wait_for_transaction_receipt(tx_hash)
                    st.success(f"Revoked **{role_choice}** from `{addr}`.")
            except Exception as e:
                st.error(f"Action failed: {e}")
