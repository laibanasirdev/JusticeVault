#!/usr/bin/env python3
"""
Compute SHA-256 hash of a file for JusticeVault submitEvidence.
Usage: python scripts/hash_evidence.py <path-to-pdf>
Output: 64-char hex (use as bytes32 in contract).
"""
import hashlib
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/hash_evidence.py <path-to-pdf>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                h.update(block)
        hex_digest = h.hexdigest()
        print(hex_digest)
        print(f"# For cast: 0x{hex_digest}", file=sys.stderr)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
