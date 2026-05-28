"""
PII detection and prompt injection defence.
Runs on every document before chunking or LLM calls.
"""
import re
import sys
from dataclasses import dataclass, field

try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

# ---------------------------------------------------------------------------
# PII patterns — structured identifiers common in Pakistani legal documents
# ---------------------------------------------------------------------------
_PII_PATTERNS: dict[str, re.Pattern] = {
    "NIC":            re.compile(r"\b\d{5}-\d{7}-\d\b"),
    "phone":          re.compile(r"\b(?:\+92|0)\d{2,3}[\s\-]?\d{7,8}\b"),
    "iban":           re.compile(r"\bPK\d{2}[A-Z]{4}\d{16}\b"),
    "account_number": re.compile(r"\b(?:A/C|Account)\s*(?:No\.?|#)\s*[\d\-]{8,20}\b", re.IGNORECASE),
    "medical_record": re.compile(r"\b(?:MRN|Patient\s+ID|Medical\s+Record(?:\s+No\.?)?)\s*:?\s*[\d\-]{4,15}\b", re.IGNORECASE),
    "credit_card":    re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"),
}

# ---------------------------------------------------------------------------
# Prompt injection signatures
# Adversarial content embedded in uploaded PDFs that tries to hijack the LLM.
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
        r"you\s+are\s+now\s+(?:a|an)\s+\w+",
        r"(?:system|assistant)\s*:\s*(?:override|bypass|ignore)",
        r"forget\s+everything",
        r"jailbreak",
        r"do\s+anything\s+now",
        r"<\|(?:system|im_start|im_end)\|>",
        r"\[INST\]",
        r"disregard\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|context)",
        r"new\s+instructions\s*:",
    ]
]


@dataclass
class ScanResult:
    safe: bool = True
    pii_detections: list[str] = field(default_factory=list)
    injection_detected: bool = False
    flags: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.flags:
            return "CLEAN"
        return " | ".join(self.flags)


def _extract_text(file_path: str) -> str:
    if not _HAS_PYPDF:
        return ""
    try:
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        print(f"⚠️  Guardrails: text extraction failed — {exc}", file=sys.stderr)
        return ""


def scan_document(file_path: str) -> ScanResult:
    """
    Scan a PDF for PII and prompt injection before any LLM call.

    PII found  → flagged in result, processing continues (legal docs contain PII by nature).
    Injection  → result.safe = False, caller must block LLM call.
    """
    result = ScanResult()
    text = _extract_text(file_path)

    if not text:
        result.flags.append("TEXT_EXTRACTION_FAILED")
        return result

    # --- PII scan ---
    for label, pattern in _PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            result.pii_detections.append(f"{label}:{len(matches)}")
            result.flags.append(f"PII:{label}")

    # --- Prompt injection scan ---
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            result.injection_detected = True
            result.safe = False
            result.flags.append("INJECTION_DETECTED")
            break  # one match is enough to block

    return result
