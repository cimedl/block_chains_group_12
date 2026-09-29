"""P1 hashing helpers for P3. Uses Python's standard library only."""

import hashlib
import json
from pathlib import Path


def identity_hash(identity):
    # All identity values are strings. Sort keys and remove extra whitespace.
    text = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "0x" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_hash(path):
    # Hash the exact stored bytes. For P3 this should be the encrypted file.
    contents = Path(path).read_bytes()
    return "0x" + hashlib.sha256(contents).hexdigest()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    identity = json.loads((root / "data/fake-identity.json").read_text())
    print("Identity hash:", identity_hash(identity))
    print("Plaintext fixture hash:", record_hash(root / "data/fake-record.json"))
    print("For real integration, encrypt the record first, then hash the encrypted file.")
