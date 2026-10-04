import os
import json
import secrets
import time

from typing import Dict, Any
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
from web3.logs import DISCARD
from crypto_utils import calculate_sha256, ensure_bytes32
from encrypt_record import decrypt_record_bytes
from storage_db import ServiceDatabase


def load_abi(contract_name: str, artifacts_dir: str = "artifacts/contracts") -> list:
    abi_path = os.path.join(artifacts_dir, f"{contract_name}.sol", f"{contract_name}.json")
    if not os.path.exists(abi_path):
        raise FileNotFoundError(f"ABI file not found: {abi_path}. Please run 'npx hardhat compile' first.")
    with open(abi_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    return artifact["abi"]


CONSUMED_REQUESTS = set()


class MedicalDataDeliveryService:
    def __init__(
        self,
        web3_provider: Web3,
        health_registry_address: str,
        health_registry_abi: list,
        consent_manager_address: str,
        consent_manager_abi: list,
        data_dir: str = "data",
        db_path: str = "service_state.db"
    ):
        self.w3 = web3_provider

        self.data_dir = data_dir

        self.chain_id = int(self.w3.eth.chain_id)
        self.namespace = str(self.chain_id) + ":" + Web3.to_checksum_address(consent_manager_address).lower()

        self.registry_namespace = str(self.chain_id) + ":" + Web3.to_checksum_address(health_registry_address).lower()
        self.db = ServiceDatabase(db_path, self.namespace)

        reg_abi = health_registry_abi or load_abi("HealthRegistry")
        consent_abi = consent_manager_abi or load_abi("ConsentManager")

        self.registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(health_registry_address),
            abi=reg_abi
        )

        self.consent_manager = self.w3.eth.contract(
            address=Web3.to_checksum_address(consent_manager_address),
            abi=consent_abi
        )

    def check_consent(self, record_id: int, requester_address: str) -> bool:

        record_id = self._uint256(record_id)
        requester = Web3.to_checksum_address(requester_address)
        grant_id = self.consent_manager.functions.latestGrantId(record_id, requester).call()
        return self.consent_manager.functions.checkPermission(grant_id, requester, record_id).call()

    @staticmethod
    def _uint256(value):
        if not isinstance(value, (int, str)):
            raise ValueError("ID must be a uint256.")
        number = int(value)

        if isinstance(value, bool) or number < 0 or number >= 2 ** 256:
            raise ValueError("ID must be a uint256.")
        return number

    def register_record_file(self, record_id: int, enc_path: str, key_path: str):
        record_id = self._uint256(record_id)
        paths = [os.path.realpath(path) for path in (enc_path, key_path)]
        root = os.path.realpath(self.data_dir)
        for path in paths:
            if os.path.commonpath([root, path]) != root:
                raise ValueError("Record files and keys must stay inside the private data directory.")
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
        with open(paths[0], "rb") as f:
            encrypted = f.read()
        onchain = self.registry.functions.getRecord(record_id).call()
        if calculate_sha256(encrypted) != ensure_bytes32(onchain[1]):
            raise ValueError("Integrity failure: registered file does not match the record commitment.")
        self.db.set_record_file(self.registry_namespace, record_id, *paths)

    def issue_delivery_challenge(self, record_id: int, requester_address: str, tx_hash: str, request_id: str) -> str:
        record_id = self._uint256(record_id)
        request_id = str(self._uint256(request_id))
        requester = Web3.to_checksum_address(requester_address)
        tx_hash = Web3.to_hex(ensure_bytes32(tx_hash))
        expires_at = int(time.time())+ 300
        message = json.dumps({"operation": "deliver_medical_record", "chain_id": self.chain_id,
            "registry": self.registry.address.lower(), "manager": self.consent_manager.address.lower(),
            "record_id": str(record_id), "request_id": request_id, "requester": requester.lower(),
            "tx_hash": tx_hash.lower(), "expires_at": expires_at, "nonce": secrets.token_hex(32)},
            sort_keys=True, separators=(",", ":"))
        self.db.add_challenge(message, record_id, request_id, requester, tx_hash, expires_at)
        return message

    def verify_requester_identity(self, requester: str, signature: str, challenge: str):
        try:
            signable = encode_defunct(text=challenge)
            recovered = Account.recover_message(signable, signature=signature)
            if recovered.lower() != requester.lower():
                raise PermissionError(f"Signature mismatch: {recovered} does not match {requester}")
        except Exception as e:
            raise PermissionError(f"Authentication failed: {str(e)}")

    def request_record_delivery(
        self,
        record_id: int,
        requester_address: str,
        signature: str,
        challenge_message: str,
        tx_hash: str,
        request_id: str
    ) -> Dict[str, Any]:
        try:
            record = self._deliver_record(record_id, requester_address, signature, challenge_message, tx_hash, request_id)
        except Exception as failure:
            self.db.record_attempt(request_id, requester_address, record_id, tx_hash, "rejected_or_failed", type(failure).__name__)
            raise
        self.db.record_attempt(request_id, requester_address, record_id, tx_hash, "returned")
        return record

    def _deliver_record(self, record_id, requester_address, signature, challenge_message, tx_hash, request_id):
        request_id = str(self._uint256(request_id))
        record_id = self._uint256(record_id)
        requester_address = Web3.to_checksum_address(requester_address)
        tx_hash = Web3.to_hex(ensure_bytes32(tx_hash))
        if int(self.w3.eth.chain_id) != self.chain_id:
            raise PermissionError("Connected chain changed after service initialization.")
        self.verify_requester_identity(requester_address, signature, challenge_message)

        if self.db.is_consumed(request_id):
            raise PermissionError(f"Security Alert: Request ID {request_id} has already been consumed.")

        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        if not receipt or receipt.get("status") != 1:
            raise ValueError("Transaction failed or receipt not found.")

        # match the request to this manager's receipt
        events = []
        for event in self.consent_manager.events.AccessDecision().process_receipt(receipt, errors=DISCARD):
            if event["address"].lower() == self.consent_manager.address.lower():
                events.append(event)
        if not events:
            raise ValueError("No AccessDecision event found in receipt.")

        matches = []
        for event in events:
            if int(event["args"]["requestId"]) == int(request_id):
                matches.append(event["args"])
        if not matches:
            raise ValueError("Request ID does not match transaction receipt.")
        requester_matches = []
        for event in matches:
            if event["requester"].lower() == requester_address.lower():
                requester_matches.append(event)
        if not requester_matches:
            raise PermissionError("Requester does not match on-chain receipt.")
        matches = []
        for event in requester_matches:
            if int(event["recordId"]) == record_id:
                matches.append(event)
        if len(matches) != 1:
            raise ValueError("Record ID does not match transaction receipt or decision is ambiguous.")
        decision = matches[0]
        if int(decision["requestId"]) != int(request_id):
            raise ValueError("Request ID does not match transaction receipt.")
        if decision["requester"].lower() != requester_address.lower():
            raise PermissionError("Requester does not match on-chain receipt.")
        if int(decision["recordId"]) != int(record_id):
            raise ValueError("Record ID does not match transaction receipt.")
        if not decision["allowed"]:
            raise PermissionError(f"Access denied on-chain: {decision.get('reason')}")

        grant_id = int(decision["grantId"])

        # consent may be revoked or expired
        is_active = self.consent_manager.functions.checkPermission(
            grant_id,
            Web3.to_checksum_address(requester_address),
            record_id
        ).call()
        if not is_active:
            raise PermissionError("Consent is no longer active (revoked or expired).")

        self.db.check_challenge(challenge_message, record_id, request_id, requester_address, tx_hash)

        paths = self.db.get_record_file(self.registry_namespace, record_id)
        if paths is None:
            raise FileNotFoundError("No private file/key mapping registered for this record.")
        enc_file_path, key_file_path = paths
        if not os.path.exists(enc_file_path):
            raise FileNotFoundError(f"Encrypted record file not found: {enc_file_path}")

        with open(enc_file_path, "rb") as f:
            encrypted_bytes = f.read()

        local_hash = calculate_sha256(encrypted_bytes)
        record_onchain = self.registry.functions.getRecord(record_id).call()
        onchain_hash = ensure_bytes32(record_onchain[1])
        if decision["patient"].lower() != record_onchain[0].lower():
            raise PermissionError("Patient does not match the registered record owner.")

        if local_hash != onchain_hash:
            raise ValueError("Integrity failure: local file hash does not match on-chain commitment.")

        if not os.path.isfile(key_file_path):
            raise FileNotFoundError(f"Decryption key not found: {key_file_path}")
        if self.w3.eth.get_block(receipt["blockNumber"])["hash"] != receipt["blockHash"]:
            raise PermissionError("Access receipt is no longer on the canonical chain.")
        if not self.consent_manager.functions.checkPermission(grant_id, requester_address, record_id).call():
            raise PermissionError("Consent is no longer active (revoked or expired).")
        # claim the request before decryption to block replay
        self.db.mark_consumed(request_id, requester_address, record_id, challenge_message)
        try:
            record = decrypt_record_bytes(encrypted_bytes, key_file_path)
        except Exception as failure:
            self.db.finish_delivery(request_id, "failed", type(failure).__name__)
            raise
        self.db.finish_delivery(request_id, "decrypted")
        return record
