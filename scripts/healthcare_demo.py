import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.logs import DISCARD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "offchain"))
from offchain_service import MedicalDataDeliveryService
from encrypt_record import encrypt_record_file
from hash_data import identity_hash


def send(web3, function, account):
    transaction = function.transact({"from": account})
    receipt = web3.eth.wait_for_transaction_receipt(transaction, timeout=20)
    if receipt.status != 1:
        raise RuntimeError("Demo transaction failed: " + Web3.to_hex(transaction))
    return receipt


def main():
    manifestPath = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".local/deployment.json"
    manifest = json.loads(manifestPath.read_text(encoding="utf-8"))
    web3 = Web3(Web3.HTTPProvider(manifest["rpcUrl"]))
    if not web3.is_connected() or web3.eth.chain_id != manifest["chainId"]:
        raise RuntimeError("Start the local node and run npm run deploy for this chain.")

    contracts = {}
    for name in ("HealthRegistry", "ConsentReward", "ConsentManager"):
        details = manifest["contracts"][name]
        receipt = web3.eth.get_transaction_receipt(details["receipt"]["transactionHash"])
        if Web3.to_hex(receipt.blockHash).lower() != details["receipt"]["blockHash"].lower():
            raise RuntimeError("Deployment manifest is stale; rerun npm run deploy.")
        contracts[name] = web3.eth.contract(address=details["address"], abi=details["abi"])
    registry = contracts["HealthRegistry"]
    manager = contracts["ConsentManager"]
    reward = contracts["ConsentReward"]

    accounts = web3.eth.accounts
    if len(accounts) < 3 or accounts[0].lower() != manifest["admin"].lower():
        raise RuntimeError("Demo needs the local deployment admin and two unlocked wallets.")
    admin, patient, doctor = accounts[:3]
    folder = manifestPath.parent / "healthcare-demo" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)

    for account, role, label in ((patient, 1, "patient"), (doctor, 2, "doctor")):
        try:
            user = registry.functions.getUser(account).call()
        except ContractLogicError:
            identity = {"synthetic": "true", "name": "Demo " + label, "email": label + "@example.invalid",
                        "personal_id": "demo-" + label, "salt": secrets.token_hex(32)}
            send(web3, registry.functions.registerUser(bytes.fromhex(identity_hash(identity)[2:]), role), account)
        else:
            if user[1] != role:
                raise RuntimeError("Local demo wallet already has a different role; use a fresh local deployment.")
        send(web3, registry.functions.setVerification(account, True), admin)
    print("Patient and doctor registered and verified.")

    record = {"synthetic": True, "record_type": "blood test panel",
              "results": [{"test": "haemoglobin", "value": 14, "unit": "g/dL"}]}
    recordPath = folder / "blood-panel.json"
    encPath = folder / "blood-panel.enc"
    keyPath = folder / "blood-panel.key"
    recordPath.write_text(json.dumps(record), encoding="utf-8")
    fileHash = encrypt_record_file(str(recordPath), str(encPath), str(keyPath))
    receipt = send(web3, registry.functions.registerRecord(bytes.fromhex(fileHash[2:]), "blood test panel"), patient)
    recordId = registry.events.RecordRegistered().process_receipt(receipt)[0]["args"]["recordId"]

    service = MedicalDataDeliveryService(web3, registry.address, registry.abi, manager.address, manager.abi,
        data_dir=str(folder), db_path=str(folder / "service_state.db"))
    service.register_record_file(recordId, str(encPath), str(keyPath))
    pointsBefore = reward.functions.balanceOf(patient).call()
    receipt = send(web3, manager.functions.grantAccess(recordId, "blood test panel", doctor, 7), patient)
    grantId = manager.events.ConsentGranted().process_receipt(receipt, errors=DISCARD)[0]["args"]["grantId"]
    if reward.functions.balanceOf(patient).call() != pointsBefore + 10:
        raise RuntimeError("The first consent should reward the patient.")
    print("Record", recordId, "registered; grant", grantId, "created and patient rewarded.")

    receipt = send(web3, manager.functions.requestAccess(recordId, grantId), doctor)
    requestId = str(manager.events.AccessDecision().process_receipt(receipt)[0]["args"]["requestId"])
    txHash = Web3.to_hex(receipt.transactionHash)
    challenge = service.issue_delivery_challenge(recordId, doctor, txHash, requestId)
    signature = Web3.to_hex(web3.eth.sign(doctor, text=challenge))
    delivered = service.request_record_delivery(recordId, doctor, signature, challenge, txHash, requestId)
    if delivered != record:
        raise RuntimeError("Delivered record differs from the synthetic original.")
    print("Doctor received the original record; local outcome recorded.")

    try:
        service.request_record_delivery(recordId, doctor, signature, challenge, txHash, requestId)
    except PermissionError:
        print("Replaying the delivered request was rejected.")
    else:
        raise RuntimeError("Replay unexpectedly succeeded.")
    send(web3, manager.functions.revokeAccess(recordId, grantId), patient)
    receipt = send(web3, manager.functions.requestAccess(recordId, grantId), doctor)
    decision = manager.events.AccessDecision().process_receipt(receipt)[0]["args"]
    if decision["allowed"]:
        raise RuntimeError("Revoked consent unexpectedly authorized access.")
    txHash = Web3.to_hex(receipt.transactionHash)
    requestId = str(decision["requestId"])
    challenge = service.issue_delivery_challenge(recordId, doctor, txHash, requestId)
    signature = Web3.to_hex(web3.eth.sign(doctor, text=challenge))
    try:
        service.request_record_delivery(recordId, doctor, signature, challenge, txHash, requestId)
    except PermissionError:
        print("Revoked delivery rejected; denied AccessDecision recorded onchain.")
    else:
        raise RuntimeError("Revoked delivery unexpectedly succeeded.")

    evidence = {"chain_id": web3.eth.chain_id, "registry": registry.address, "manager": manager.address,
        "record_id": recordId, "grant_id": grantId, "final_denied_request_id": requestId,
        "result": "delivered, replay rejected, revoked delivery rejected",
        "storage": str(folder)}
    (folder / "workflow.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Workflow complete. Local evidence:", folder)


if __name__ == "__main__":
    main()
