"""Pytest for Oracle logic: file integrity verification (Zero Trust)."""
import pytest

from oracle_utils import verify_file_integrity


def test_verify_file_integrity_matches(temp_pdf, expected_hash_hex):
    """When file hash matches expected hex, returns True."""
    assert verify_file_integrity(temp_pdf, expected_hash_hex) is True
    assert verify_file_integrity(temp_pdf, "0x" + expected_hash_hex) is True
    assert verify_file_integrity(temp_pdf, expected_hash_hex.upper()) is True


def test_verify_file_integrity_mismatch(temp_pdf):
    """When file hash does not match, returns False."""
    wrong_hash = "0" * 64
    assert verify_file_integrity(temp_pdf, wrong_hash) is False


def test_verify_file_integrity_nonexistent_file():
    """When file does not exist, returns False (no exception)."""
    assert verify_file_integrity("/nonexistent/path/file.pdf", "0" * 64) is False


def test_verify_file_integrity_expected_as_bytes(temp_pdf, expected_hash_hex):
    """Expected hash can be passed as bytes (e.g. from contract)."""
    hash_bytes = bytes.fromhex(expected_hash_hex)
    assert verify_file_integrity(temp_pdf, hash_bytes) is True
