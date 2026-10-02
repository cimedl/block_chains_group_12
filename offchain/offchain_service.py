import os
import json
from typing import Dict, Any
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

from crypto_utils import calculate_sha256, ensure_bytes32
from encrypt_record import decrypt_record_file, encrypt_record_file
from storage_db import ServiceDatabase

# Signature Verification
# Integrity Check
# Replay Prevention
# Decryption

def load_abi(contract_name: str, artifacts_dir: str = "artifacts/contracts") -> list:
    """Load contract ABI from Hardhat build artifacts."""
    abi_path = os.path.join(artifacts_dir, f"{contract_name}.sol", f"{contract_name}.json")
    if not os.path.exists(abi_path):
        raise FileNotFoundError(f"ABI file not found: {abi_path}. Please run 'npx hardhat compile' first.")
    with open(abi_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    return artifact["abi"]

CONSUMED_REQUESTS = set() # Record the IDs of processed requests to prevent duplicate claims.

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
        self.db = ServiceDatabase(db_path)

        reg_abi = health_registry_abi or load_abi("HealthRegistry")
        consent_abi = consent_manager_abi or load_abi("ConsentManager")

        # Bind the smart contract
        self.registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(health_registry_address),
            abi=reg_abi
        )
        self.consent_manager = self.w3.eth.contract(
            address=Web3.to_checksum_address(consent_manager_address),
            abi=consent_abi
        )

    def check_consent(self, user_address: str, requester_address: str) -> bool:
        try:
            is_granted = self.consent_manager.functions.isConsentGranted(
                self.w3.to_checksum_address(user_address),
                self.w3.to_checksum_address(requester_address)
            ).call()
            return is_granted
        except Exception as e:
            print(f"Error checking consent: {e}")
            return False

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
        # Verify authorization and deliver the decrypted record data.
        self.verify_requester_identity(requester_address, signature, challenge_message)

        # Replay check
        if self.db.is_consumed(request_id):
            raise PermissionError(f"Security Alert: Request ID {request_id} has already been consumed.")

        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        if not receipt or receipt.get("status") != 1:
            raise ValueError("Transaction failed or receipt not found.")

        events = self.consent_manager.events.AccessDecision().process_receipt(receipt)
        if not events:
            raise ValueError("No AccessDecision event found in receipt.")
        
        decision = events[0]["args"]
        #if str(decision["requestId"]) != str(request_id):
        if int(decision["requestId"]) != int(request_id):
            raise ValueError("Request ID does not match transaction receipt.")
        if decision["requester"].lower() != requester_address.lower():
            raise PermissionError("Requester does not match on-chain receipt.")
        #if decision["recordId"] != record_id:
        if int(decision["recordId"]) != int(record_id):
            raise ValueError("Record ID does not match transaction receipt.")
        if not decision["allowed"]:
            raise PermissionError(f"Access denied on-chain: {decision.get('reason')}")

        #grant_id = decision.get("grantId")
        grant_id = int(decision["grantId"])

        # Double check current consent status
        is_active = self.consent_manager.functions.checkPermission(
            grant_id,
            Web3.to_checksum_address(requester_address),
            record_id
        ).call()
        if not is_active:
            raise PermissionError("Consent is no longer active (revoked or expired).")

        # File integrity check
        enc_file_path = os.path.join(self.data_dir, "fake-record.enc")
        if not os.path.exists(enc_file_path):
            raise FileNotFoundError(f"Encrypted record file not found: {enc_file_path}")

        with open(enc_file_path, "rb") as f:
            encrypted_bytes = f.read()

        local_hash = calculate_sha256(encrypted_bytes)
        record_onchain = self.registry.functions.getRecord(record_id).call()
        onchain_hash = ensure_bytes32(record_onchain[1])

        if local_hash != onchain_hash:
            raise ValueError("Integrity failure: local file hash does not match on-chain commitment.")

        # Mark request as consumed
        self.db.mark_consumed(request_id, requester_address, record_id)

        key_file_path = os.path.join(self.data_dir, "secret.key")
        return decrypt_record_file(enc_path=enc_file_path, key_path=key_file_path)
        #return decrypt_record_file(enc_path=enc_file_path)


    