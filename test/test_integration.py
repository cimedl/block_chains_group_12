"""Check that the contract and Python file sharing work together."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from education import EducationDemo, DIPLOMA, TRANSCRIPT, record_hash, sample_identity, sample_diploma


class EducationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.demo = EducationDemo(self.temp.name)
        self.demo.deploy()
        self.student = self.demo.accounts[1]
        self.employer = self.demo.accounts[2]
        self.other = self.demo.accounts[3]
        self.demo.register(self.student, sample_identity())
        self.record = sample_diploma()
        self.demo.publish(self.student, DIPLOMA, self.record)

    def test_complete_workflow_and_persistent_audit(self):
        self.assertFalse(self.demo.access(self.student, self.employer)["allowed"])
        self.demo.grant(self.student, self.employer)
        self.assertEqual(self.demo.access(self.student, self.employer)["record"], self.record)
        self.demo.revoke(self.student, self.employer)
        self.assertFalse(self.demo.access(self.student, self.employer)["allowed"])
        logs = self.demo.contract.events.AccessLogged().get_logs(from_block=0)
        decisions = []
        for log in logs:
            event = log["args"]
            decisions.append(event["allowed"])
            self.assertEqual(event["requester"], self.employer)
            self.assertEqual(event["student"], self.student)
            self.assertEqual(event["dataType"], DIPLOMA)
            self.assertGreater(event["timestamp"], 0)
        self.assertEqual(decisions, [False, True, False])

    def test_expiry_prevents_file_release(self):
        self.demo.grant(self.student, self.employer)
        self.demo.advance_time(86400)
        result = self.demo.access(self.student, self.employer)
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["record"])

    def test_wrong_requester_is_denied(self):
        self.demo.grant(self.student, self.employer)
        self.assertFalse(self.demo.access(self.student, self.other)["allowed"])

    def test_wrong_data_type_is_denied(self):
        self.demo.grant(self.student, self.employer)
        self.assertFalse(self.demo.access(self.student, self.employer, TRANSCRIPT)["allowed"])

    def test_tampered_local_record_is_rejected(self):
        self.demo.grant(self.student, self.employer)
        path = self.demo.record_path(self.student, DIPLOMA)
        changed_record = self.record.copy()
        changed_record["degree"] = "Tampered degree"
        path.write_text(json.dumps(changed_record))
        result = self.demo.access(self.student, self.employer)
        self.assertEqual(result["reason"], "Record hash mismatch")
        self.assertIsNone(result["record"])

    def test_missing_local_record_is_rejected(self):
        self.demo.grant(self.student, self.employer)
        self.demo.record_path(self.student, DIPLOMA).unlink()
        self.assertEqual(self.demo.access(self.student, self.employer)["reason"], "Local file missing")

    def test_two_students_control_separate_records(self):
        self.demo.register(self.other, sample_identity(2))
        self.demo.publish(self.other, DIPLOMA, sample_diploma(2))
        self.demo.grant(self.student, self.employer)
        self.assertTrue(self.demo.access(self.student, self.employer)["allowed"])
        self.assertFalse(self.demo.access(self.other, self.employer)["allowed"])

    def test_rewards_are_not_paid_on_access_or_regrant(self):
        self.demo.grant(self.student, self.employer)
        for _ in range(3):
            self.assertTrue(self.demo.access(self.student, self.employer)["allowed"])
        self.demo.revoke(self.student, self.employer)
        self.demo.grant(self.student, self.employer)
        self.assertEqual(self.demo.contract.functions.rewardBalance(self.student).call(), 10)
        self.assertEqual(self.demo.contract.functions.rewardBalance(self.employer).call(), 0)

    def test_hash_ignores_dictionary_key_order(self):
        self.assertEqual(record_hash({"a": 1, "b": 2}), record_hash({"b": 2, "a": 1}))

    def test_salts_make_identical_attributes_have_different_hashes(self):
        self.assertNotEqual(record_hash(sample_identity()), record_hash(sample_identity()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
