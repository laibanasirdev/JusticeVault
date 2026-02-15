"""
Pure Oracle utilities: file integrity verification (no Web3 or AI deps).
Used by the Oracle (monitor) and testable by Pytest without a live chain.
"""
import hashlib


def verify_file_integrity(file_path, expected_hash_hex):
    """
    Verify that the file at file_path has SHA-256 hash matching expected_hash_hex.
    First Principles: Don't trust the IPFS gateway — verify the digital fingerprint.

    :param file_path: Path to the file.
    :param expected_hash_hex: Expected hash as bytes32 (HexBytes/bytes) or hex string (with or without 0x).
    :return: True if the file's SHA-256 matches, False otherwise or on error.
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        actual_hash = sha256_hash.hexdigest()

        if isinstance(expected_hash_hex, bytes):
            clean_expected = expected_hash_hex.hex()
        elif hasattr(expected_hash_hex, "hex"):
            clean_expected = expected_hash_hex.hex()
        else:
            clean_expected = str(expected_hash_hex)
        clean_expected = clean_expected.replace("0x", "").lower()
        actual_hash = actual_hash.lower()

        return actual_hash == clean_expected
    except Exception:
        return False
