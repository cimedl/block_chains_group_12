import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hash_data import identity_hash, record_hash


class HashDataTest(unittest.TestCase):
    def test_identity_key_order_does_not_matter(self):
        self.assertEqual(identity_hash({"name": "Demo", "salt": "abc"}),
                         identity_hash({"salt": "abc", "name": "Demo"}))

    def test_identity_matches_documented_encoding(self):
        expected = hashlib.sha256(b'{"name":"Demo","salt":"abc"}').hexdigest()
        self.assertEqual(identity_hash({"name": "Demo", "salt": "abc"}), "0x" + expected)

    def test_salt_changes_hash(self):
        self.assertNotEqual(identity_hash({"name": "Demo", "salt": "abc"}),
                            identity_hash({"name": "Demo", "salt": "def"}))

    def test_file_hash_uses_exact_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "record.bin"
            path.write_bytes(b"abc")
            self.assertEqual(record_hash(path),
                             "0xba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            original = record_hash(path)
            path.write_bytes(b"abc\n")
            self.assertNotEqual(original, record_hash(path))

    def test_fixtures_match_proposed_schema(self):
        data = Path(__file__).resolve().parents[1] / "data"
        identity = json.loads((data / "fake-identity.json").read_text())
        record = json.loads((data / "fake-record.json").read_text())
        self.assertEqual(set(identity), {"name", "email", "personal_id", "date_of_birth", "salt"})
        self.assertTrue(all(isinstance(value, str) for value in identity.values()))
        self.assertEqual(len(bytes.fromhex(identity["salt"])), 32)
        self.assertEqual(record["schema_version"], "1")
        self.assertEqual(len(bytes.fromhex(record["salt"])), 32)
        self.assertGreater(len(record["results"]), 0)
        for result in record["results"]:
            self.assertEqual(set(result), {"test", "value", "unit"})


if __name__ == "__main__":
    unittest.main()
