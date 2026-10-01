import json
from pathlib import Path
from web3 import Web3
from service.file_service import get_file
# run the end-to-end demonstration

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_FILE = ROOT / ".local" / "deployment.json"
SEED_FILE = ROOT / "data" / "seed.json"

REASONS = {
    0: "NO_CONSENT",
    1: "EXPIRED",
    2: "REVOKED",
    3: "UNKNOWN_RECORD",
    4: "UNREGISTERED_REQUESTER",
    5: "GRANTED",
    6: "PATIENT_NOT_VERIFIED",
}


def contract(name, address):
    # Load a compiled Hardhat contract

    path = ROOT / "artifacts" / "contracts" / f"{name}.sol" / f"{name}.json"

    with open(path, encoding="utf-8") as f:
        abi = json.load(f)["abi"]

    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=abi,
    )


def send(fn, sender):
    # Send a transaction using an unlocked Hardhat account

    tx = fn.build_transaction({
        "from": sender,
        "nonce": w3.eth.get_transaction_count(sender),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price,
    })

    tx_hash = w3.eth.send_transaction(tx)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt["status"] != 1:
        raise RuntimeError("Transaction failed")

    return receipt


def access_result(receipt):
    # Read and display the AccessDecision event

    event = consent_manager.events.AccessDecision().process_receipt(receipt)[0]
    args = event["args"]

    allowed = args["allowed"]
    reason = REASONS[int(args["reason"])]

    print(f"    allowed = {allowed}")
    print(f"    reason  = {reason}")

    return allowed, reason


def main():
    global w3, consent_manager

    print("\n---HEALTHCARE BLOCKCHAIN ACCESS DEMO---")

   ########################
    # Setup
   ########################

    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

    with open(DEPLOYMENT_FILE, encoding="utf-8") as f:
        deployment = json.load(f)

    with open(SEED_FILE, encoding="utf-8") as f:
        records = json.load(f)

    accounts = w3.eth.accounts

    patient = accounts[1]  # Alice
    doctor = accounts[3]   # Carol

    registry = contract(
        "HealthRegistry",
        deployment["contracts"]["HealthRegistry"]["address"],
    )

    consent_manager = contract(
        "ConsentManager",
        deployment["contracts"]["ConsentManager"]["address"],
    )

    # Find Alice's first record
    alice = next(
        r for r in records
        if Web3.to_checksum_address(r["patient"])
        == Web3.to_checksum_address(patient)
    )

    record_id = int(alice["record_id"])
    record_type = alice["record_type"]
    record_path = Path(alice["path"])

    print(f"Alice: {patient}")
    print(f"Carol: {doctor}")
    print(f"Record ID: {record_id}")

   ########################
    # 1. No consent
   ########################

    print("\n1. Access before consent")

    receipt = send(
        consent_manager.functions.requestAccess(record_id, 0),
        doctor,
    )

    allowed, reason = access_result(receipt)

    assert not allowed
    assert reason == "NO_CONSENT"

   ########################
    # 2. Grant consent
   ########################

    print("\n2. Grant consent")

    receipt = send(
        consent_manager.functions.grantAccess(
            record_id,
            record_type,
            doctor,
            7,
        ),
        patient,
    )

    event = consent_manager.events.ConsentGranted().process_receipt(receipt)[0]
    grant_id = event["args"]["grantId"]

    print(f"    grantId = {grant_id}")
    print("    RESULT: CONSENT GRANTED")

   ########################
    # 3. Access allowed
   ########################

    print("\n3. Doctor accesses record")

    receipt = send(
        consent_manager.functions.requestAccess(
            record_id,
            grant_id,
        ),
        doctor,
    )

    allowed, reason = access_result(receipt)

    assert allowed
    assert reason == "GRANTED"

    # Also demonstrate the read-only permission check
    permission = consent_manager.functions.checkPermission(
        grant_id,
        doctor,
        record_id,
    ).call()

    print(f"    checkPermission() = {permission}")

   ########################
    # 4. Verify hash
   ########################

    print("\n4. Verify record integrity")

    medical_record = get_file(
        registry,
        consent_manager,
        record_id,
        grant_id,
        doctor,
        record_path,
    )

    assert medical_record is not None

    print("    RESULT: HASH MATCH")
    print("    RESULT: RECORD RETRIEVED")

   ########################
    # 5. Revoke consent
   ########################

    print("\n5. Patient revokes consent")

    send(
        consent_manager.functions.revokeAccess(
            record_id,
            grant_id,
        ),
        patient,
    )

    permission = consent_manager.functions.checkPermission(
        grant_id,
        doctor,
        record_id,
    ).call()

    print(f"    checkPermission() = {permission}")

    # Try the actual access request as well.
    receipt = send(
        consent_manager.functions.requestAccess(
            record_id,
            grant_id,
        ),
        doctor,
    )

    allowed, reason = access_result(receipt)

    assert not allowed
    assert reason == "REVOKED"

    print("    RESULT: REVOKED")

   ########################
    # 6. Expiry
   ########################

    print("\n6. Access after expiry")

    # Create a second grant that will later expire
    receipt = send(
        consent_manager.functions.grantAccess(
            record_id,
            record_type,
            doctor,
            1,
        ),
        patient,
    )

    event = consent_manager.events.ConsentGranted().process_receipt(receipt)[0]
    grant_id = event["args"]["grantId"]

    print(f"    New grantId = {grant_id}")

    # Move the local Hardhat blockchain forward
    w3.provider.make_request("evm_increaseTime", [2 * 24 * 60 * 60])
    w3.provider.make_request("evm_mine", [])

    receipt = send(
        consent_manager.functions.requestAccess(
            record_id,
            grant_id,
        ),
        doctor,
    )

    allowed, reason = access_result(receipt)

    assert not allowed
    assert reason == "EXPIRED"

    print("    RESULT: EXPIRED")

    print("\n---DEMO COMPLETED---")


if __name__ == "__main__":
    main()