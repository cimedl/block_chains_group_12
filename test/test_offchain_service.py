import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.logs import DISCARD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "offchain"))

from encrypt_record import encrypt_record_file
from offchain_service import MedicalDataDeliveryService



class OffchainServiceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        contracts = ("HealthRegistry", "ConsentReward", "ConsentManager")
        for name in contracts:
            artifact = ROOT / "artifacts" / "contracts" / (name + ".sol") / (name + ".json")
            if not artifact.exists():
                raise RuntimeError("Run npx hardhat compile before the file-delivery tests")

        nodePath = shutil.which("node")
        if nodePath is None:
            raise RuntimeError("Node.js is needed to start the temporary Hardhat blockchain")

        cls.nodeFolder = tempfile.TemporaryDirectory(prefix="p4-blockchain-")
        cls.addClassCleanup(cls.nodeFolder.cleanup)
        cls.nodeLog = open(Path(cls.nodeFolder.name) / "node.log", "w", encoding="utf-8")
        cls.addClassCleanup(cls.nodeLog.close)

        with socket.socket() as portSocket:
            portSocket.bind(("127.0.0.1", 0))
            port = portSocket.getsockname()[1]

        cls.node = subprocess.Popen(
            [nodePath, str(ROOT / "node_modules/hardhat/dist/src/cli.js"),
             "node", "--hostname", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            stdout=cls.nodeLog,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        cls.addClassCleanup(cls.stopNode)

        cls.w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:" + str(port), request_kwargs={"timeout": 2}))
        deadline = time.monotonic() + 20

        while time.monotonic() < deadline:
            if cls.node.poll() is not None:
                raise RuntimeError("Temporary Hardhat node stopped with exit code " + str(cls.node.returncode))
            if cls.w3.is_connected():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Temporary Hardhat node did not start within 20 seconds")

    @classmethod
    def stopNode(cls):
        if cls.node.poll() is None:
            cls.node.terminate()
            try:
                cls.node.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.node.kill()
                cls.node.wait(timeout=5)


    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="p4-record-")
        self.addCleanup(self.folder.cleanup)
        self.data = Path(self.folder.name)

        self.admin, self.patient, self.doctor = self.w3.eth.accounts[:3]
        self.registry = self.deploy("HealthRegistry", self.admin)
        self.reward = self.deploy("ConsentReward", self.registry.address, self.admin)
        self.manager = self.deploy("ConsentManager", self.registry.address, self.reward.address)

        self.send(self.reward.functions.setConsentManager(self.manager.address), self.admin)

        identityHash = hashlib.sha256(b"synthetic patient identity and salt").digest()
        doctorIdHash = hashlib.sha256(b"synthetic doctor identity and salt").digest()

        # Role.Patient is 1 and Role.Doctor is 2 in IHealthRegistry.
        self.send(self.registry.functions.registerUser(identityHash,1), self.patient)
        self.send(self.registry.functions.setVerification(self.patient, True), self.admin)
        self.send(self.registry.functions.registerUser(doctorIdHash, 2), self.doctor)
        self.send(self.registry.functions.setVerification(self.doctor,True), self.admin)


    def send(self, function, sender):
        txHash = function.transact({"from": sender})
        receipt = self.w3.eth.wait_for_transaction_receipt(txHash, timeout=20)
        self.assertEqual(receipt.status, 1, "transaction should succeed")
        return receipt

    def deploy(self, name, *args):
        artifactPath = ROOT / "artifacts" / "contracts" / (name + ".sol") / (name + ".json")
        artifact = json.loads(artifactPath.read_text(encoding="utf-8"))
        contract = self.w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])

        receipt = self.send(contract.constructor(*args), self.admin)
        self.assertIsNotNone(receipt.contractAddress, "contract should be deployed")

        return self.w3.eth.contract(address=receipt.contractAddress, abi=artifact["abi"])


    def test_DoctorReceivesBloodPanelWithConsent(self):
        record = {
            "synthetic": True,
            "record_type": "blood test panel",
            "results": [{"test": "haemoglobin", "value": 14, "unit": "g/dL"}]
        }

        recordPath = self.data / "fake-record.json"
        encPath = self.data / "fake-record.enc"
        keyPath = self.data / "secret.key"
        recordPath.write_text(json.dumps(record), encoding="utf-8")

        # The delivery service commits to the encrypted file, rather than the JSON text.
        fileHash = encrypt_record_file(str(recordPath),str(encPath), str(keyPath))
        receipt = self.send(
            self.registry.functions.registerRecord(bytes.fromhex(fileHash[2:]), "blood test panel"),
            self.patient
        )
        records = self.registry.events.RecordRegistered().process_receipt(receipt)
        self.assertEqual(len(records), 1, "one blood panel should be registered")
        recordId = records[0]["args"]["recordId"]

        storedRecord = self.registry.functions.getRecord(recordId).call()
        self.assertEqual(storedRecord[0], self.patient, "patient must own the record")
        self.assertEqual(bytes(storedRecord[1]), hashlib.sha256(encPath.read_bytes()).digest(), "encrypted file hashes must match")

        receipt = self.send(
            self.manager.functions.grantAccess(recordId,"blood test panel", self.doctor,7),
            self.patient
        )
        grants = self.manager.events.ConsentGranted().process_receipt(receipt, errors=DISCARD)
        self.assertEqual(len(grants), 1, "one consent grant should be created")
        grantId = grants[0]["args"]["grantId"]

        receipt = self.send(self.manager.functions.requestAccess(recordId,grantId), self.doctor)
        decisions = self.manager.events.AccessDecision().process_receipt(receipt)
        self.assertEqual(len(decisions), 1, "doctor request should have an audit decision")
        decision = decisions[0]["args"]
        requestId = decision["requestId"]

        self.assertTrue(decision["allowed"], "consent should allow the doctor to read the panel")
        self.assertEqual(decision["requester"], self.doctor, "doctor must match the receipt")
        self.assertEqual(decision["recordId"], recordId, "record ids must match")
        self.assertEqual(decision["grantId"], grantId, "grant ids must match")

        service = MedicalDataDeliveryService(
            self.w3, self.registry.address, self.registry.abi,
            self.manager.address, self.manager.abi,
            data_dir=str(self.data), db_path=str(self.data / "service_state.db")
        )
        service.register_record_file(recordId, str(encPath), str(keyPath))

        # The service issues a single-use challenge; the doctor signs it with the temporary node's wallet.
        challenge = service.issue_delivery_challenge(recordId, self.doctor, Web3.to_hex(receipt.transactionHash), str(requestId))
        signature = self.w3.eth.sign(self.doctor, text=challenge)
        signer = Account.recover_message(encode_defunct(text=challenge), signature=signature)
        self.assertEqual(signer.lower(), self.doctor.lower(), "signature must belong to the doctor")

        delivered = service.request_record_delivery(
            record_id=recordId,
            requester_address=self.doctor,
            signature=Web3.to_hex(signature),
            challenge_message=challenge,
            tx_hash=Web3.to_hex(receipt.transactionHash),
            request_id=str(requestId)
        )

        self.assertEqual(delivered, record, "delivered blood panel must match the original data")
        self.assertTrue(service.db.is_consumed(str(requestId)), "successful delivery should consume the request")
        self.assertEqual(self.reward.functions.balanceOf(self.patient).call(), 10, "patient should get 10 points")
        self.assertEqual(self.reward.functions.balanceOf(self.doctor).call(), 0, "doctor should not need points for access")


    def test_WrongWalletCannotReceiveBloodPanel(self):
        record = {
            "synthetic": True,
            "record_type": "blood test panel",
            "results": [{"test": "haemoglobin", "value": 14, "unit": "g/dL"}]
        }

        recordPath = self.data / "fake-record.json"
        encPath = self.data / "fake-record.enc"
        keyPath = self.data / "secret.key"
        recordPath.write_text(json.dumps(record), encoding="utf-8")

        fileHash = encrypt_record_file(str(recordPath),str(encPath), str(keyPath))
        receipt = self.send(
            self.registry.functions.registerRecord(bytes.fromhex(fileHash[2:]), "blood test panel"),
            self.patient
        )
        recordId = self.registry.events.RecordRegistered().process_receipt(receipt)[0]["args"]["recordId"]

        receipt = self.send(
            self.manager.functions.grantAccess(recordId,"blood test panel", self.doctor,7),
            self.patient
        )
        grantId = self.manager.events.ConsentGranted().process_receipt(receipt, errors=DISCARD)[0]["args"]["grantId"]

        receipt = self.send(self.manager.functions.requestAccess(recordId,grantId), self.doctor)
        decision = self.manager.events.AccessDecision().process_receipt(receipt)[0]["args"]
        requestId = decision["requestId"]
        self.assertTrue(decision["allowed"], "the doctor should have an allowed receipt before testing the signature")

        service = MedicalDataDeliveryService(
            self.w3, self.registry.address, self.registry.abi,
            self.manager.address, self.manager.abi,
            data_dir=str(self.data), db_path=str(self.data / "service_state.db")
        )
        service.register_record_file(recordId, str(encPath), str(keyPath))

        # Claim to be the doctor, but sign the doctor's challenge using the patient's wallet.
        challenge = service.issue_delivery_challenge(recordId, self.doctor, Web3.to_hex(receipt.transactionHash), str(requestId))
        signature = self.w3.eth.sign(self.patient, text=challenge)
        signer = Account.recover_message(encode_defunct(text=challenge), signature=signature)
        self.assertEqual(signer.lower(), self.patient.lower(), "this signature should belong to the patient")

        request = {
            "record_id": recordId,
            "requester_address": self.doctor,
            "signature": Web3.to_hex(signature),
            "challenge_message": challenge,
            "tx_hash": Web3.to_hex(receipt.transactionHash),
            "request_id": str(requestId)
        }

        self.assertFalse(service.db.is_consumed(str(requestId)), "the request should be unused")

        with self.assertRaisesRegex(PermissionError, "Signature mismatch"):
            service.request_record_delivery(**request)

        self.assertFalse(service.db.is_consumed(str(requestId)), "wrong wallet should not consume the doctor's request")

        # The same receipt should still work when the doctor supplies their own proof.
        doctorSignature = self.w3.eth.sign(self.doctor, text=challenge)
        request["signature"] = Web3.to_hex(doctorSignature)
        delivered = service.request_record_delivery(**request)

        self.assertEqual(delivered, record, "the doctor should still receive the original blood panel")
        self.assertTrue(service.db.is_consumed(str(requestId)), "only the successful delivery should consume the request")


if __name__ == "__main__":
    unittest.main()
