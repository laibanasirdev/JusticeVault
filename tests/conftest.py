"""Pytest fixtures for JusticeVault tests."""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts to path so we can import oracle_utils
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def temp_pdf():
    """A minimal PDF-like binary file with known content for hashing tests."""
    content = b"%PDF-1.4 sample legal document content for testing\n"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name
    try:
        os.unlink(f.name)
    except FileNotFoundError:
        pass


@pytest.fixture
def expected_hash_hex(temp_pdf):
    """SHA-256 hash of the temp PDF content."""
    with open(temp_pdf, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
