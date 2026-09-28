"""Functions for the local education demo. Only use fake student data here."""

import json
import secrets
import time
from pathlib import Path

from web3 import Web3
from web3.logs import DISCARD

ROOT = Path(__file__).resolve().parents[1]
DIPLOMA = 0
TRANSCRIPT = 1
CERTIFICATE = 2


def record_hash(record):
    """Sort the keys so the same record always gives the same hash."""
    text = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return Web3.keccak(text=text)


def sample_identity(number=1):
    return {
        "name": f"Demo Student {number}",
        "email": f"student{number}@example.invalid",
        "student_id": f"DEMO-{number:03}",
        "degree": "BSc Computer Science",
        # Random text makes the hash harder to guess.
        "salt": secrets.token_hex(32),
    }


def sample_diploma(number=1):
    return {
        "student_id": f"DEMO-{number:03}",
        "degree": "BSc Computer Science",
        "institution": "Fictional Demo University",
        "year": 2026,
        # Random text makes the hash harder to guess.
        "salt": secrets.token_hex(32),
    }


# Keep the connection, contract and file folder together in one object.
class EducationDemo:
    def __init__(self, storage_directory, rpc_url="http://127.0.0.1:8545"):
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise RuntimeError("Start the local blockchain first: npm run node")
        if self.web3.eth.chain_id != 31337:
            raise RuntimeError("This demo only runs on a local Hardhat chain (31337)")
        self.accounts = self.web3.eth.accounts
        self.storage = Path(storage_directory)
        self.storage.mkdir(parents=True, exist_ok=True)
        self.measurements = []
        artifact = ROOT / "artifacts/contracts/EduConsent.sol/EduConsent.json"
        self.artifact = json.loads(artifact.read_text())
        self.contract = None

    def send(self, function, sender, label):
        """Send the transaction and save its gas use for the assignment."""
        started = time.perf_counter()
        transaction = function.transact({"from": sender})
        receipt = self.web3.eth.wait_for_transaction_receipt(transaction)
        elapsed = (time.perf_counter() - started) * 1000
        if receipt.status != 1:
            raise RuntimeError(f"Transaction failed: {label}")
        self.measurements.append({
            "function": label,
            "gas": receipt.gasUsed,
            "confirmation_ms": round(elapsed, 3),
            "transaction": transaction.to_0x_hex(),
        })
        return receipt

    def deploy(self):
        factory = self.web3.eth.contract(
            abi=self.artifact["abi"], bytecode=self.artifact["bytecode"]
        )
        receipt = self.send(factory.constructor(), self.accounts[0], "deployment")
        self.contract = self.web3.eth.contract(
            address=receipt.contractAddress, abi=self.artifact["abi"]
        )
        return receipt.contractAddress

    def register(self, student, identity):
        identity_hash = record_hash(identity)
        function = self.contract.functions.register(identity_hash)
        receipt = self.send(function, student, "register")
        path = self.storage / f"{student.lower()}-identity.json"
        path.write_text(json.dumps(identity, indent=2) + "\n")
        return receipt

    def record_path(self, student, data_type):
        return self.storage / f"{student.lower()}-{int(data_type)}.json"

    def publish(self, student, data_type, record):
        file_hash = record_hash(record)
        function = self.contract.functions.publishData(data_type, file_hash)
        receipt = self.send(function, student, "publishData")
        path = self.record_path(student, data_type)
        path.write_text(json.dumps(record, indent=2) + "\n")
        return receipt

    def grant(self, student, requester, data_type=DIPLOMA, days=1):
        function = self.contract.functions.grantConsent(requester, data_type, days)
        return self.send(function, student, "grantConsent")

    def revoke(self, student, requester, data_type=DIPLOMA):
        function = self.contract.functions.revokeConsent(requester, data_type)
        return self.send(function, student, "revokeConsent")

    def access(self, student, requester, data_type=DIPLOMA):
        """Ask the contract for access before reading the student's file."""
        function = self.contract.functions.requestAccess(student, data_type)
        receipt = self.send(function, requester, "requestAccess")
        events = self.contract.events.AccessLogged().process_receipt(receipt, errors=DISCARD)
        event = events[0]["args"]
        if not event["allowed"]:
            return {"allowed": False, "reason": "No valid consent", "record": None}

        # Check again in case the student revoked consent after the access transaction.
        consent = self.contract.functions.hasConsent(student, requester, data_type).call()
        if not consent:
            return {"allowed": False, "reason": "Consent changed", "record": None}

        path = self.record_path(student, data_type)
        if not path.exists():
            return {"allowed": False, "reason": "Local file missing", "record": None}
        record = json.loads(path.read_text())
        current_hash = self.contract.functions.dataHashes(student, data_type).call()
        file_hash = record_hash(record)
        if file_hash != event["dataHash"] or file_hash != current_hash:
            return {"allowed": False, "reason": "Record hash mismatch", "record": None}
        return {"allowed": True, "reason": "Valid consent and matching hash", "record": record}

    def advance_time(self, seconds):
        """Skip time on the test blockchain instead of waiting a whole day."""
        reply = self.web3.provider.make_request("evm_increaseTime", [seconds])
        if "error" in reply:
            raise RuntimeError(reply["error"])

        # Make a block so the new time takes effect.
        reply = self.web3.provider.make_request("evm_mine", [])
        if "error" in reply:
            raise RuntimeError(reply["error"])
