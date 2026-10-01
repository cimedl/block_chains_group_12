# file_service.py

#
import json
import hashlib
from pathlib import Path
from web3 import Web3


ROOT = Path(__file__).resolve().parents[1]


def load_contract(name, address, w3):
    # Load a compiled Hardhat contract

    path = ROOT / "artifacts" / "contracts" / f"{name}.sol" / f"{name}.json"

    with open(path, encoding="utf-8") as f:
        abi = json.load(f)["abi"]

    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=abi,
    )


def hash_file(path):
    # Calculate the SHA-256 hash of a local file

    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).digest()


def check_permission(consent_manager, grant_id, requester, record_id):
    # Check whether the requester currently has permission

    return consent_manager.functions.checkPermission(
        grant_id,
        requester,
        record_id,
    ).call()


def verify_file(registry, record_id, file_path):
    # Compare the local file hash with the hash stored on-chain

    local_hash = hash_file(file_path)

    record = registry.functions.getRecord(record_id).call()
    blockchain_hash = record[1]

    return local_hash == blockchain_hash


def get_file(
    registry,
    consent_manager,
    record_id,
    grant_id,
    requester,
    file_path,
):
    # Check permission before returning the medical record

    allowed = check_permission(
        consent_manager,
        grant_id,
        requester,
        record_id,
    )

    if not allowed:
        return None

    # Verify that the file has not been changed

    if not verify_file(registry, record_id, file_path):
        return None

    # Read and return the medical record

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)