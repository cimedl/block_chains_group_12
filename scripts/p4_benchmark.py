import argparse
import contextlib
import csv
import hashlib
import io
import json
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "test"))
from test_offchain_service import OffchainServiceTest, MedicalDataDeliveryService, encrypt_record_file
from web3 import Web3
from web3.logs import DISCARD
from p4_verify import environment


def saveCsv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w",encoding="utf-8",newline="") as output:
        writer = csv.DictWriter(output,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class Workload:
    def __init__(self, w3, patients, repetition, folder):
        self.w3 = w3
        self.patients = patients
        self.repetition = repetition
        self.folder = folder
        self.transactions = []
        self.receipts = []
        self.deliveries = []
        self.admin, self.doctor, self.otherDoctor = w3.eth.accounts[:3]

    def send(self, function, sender, operation):
        start = time.perf_counter()
        txHash = function.transact({"from": sender})
        submitted = time.perf_counter()
        receipt = self.w3.eth.wait_for_transaction_receipt(txHash,timeout=20)
        confirmed = time.perf_counter()
        if receipt.status != 1:
            raise RuntimeError("Transaction failed: " + Web3.to_hex(txHash))
        self.receipts.append({"patients": self.patients, "repetition": self.repetition,
            "operation": operation, "receipt": json.loads(Web3.to_json(receipt))})
        sample = {"patients": self.patients, "repetition": self.repetition, "operation": operation,
            "sender": sender, "transaction_hash": Web3.to_hex(txHash), "block_number": receipt.blockNumber,
            "status": receipt.status, "contract_address": receipt.contractAddress or "", "to": receipt.to or "",
            "gas_used": receipt.gasUsed, "effective_gas_price_wei": receipt.effectiveGasPrice,
            "fee_wei": receipt.gasUsed * receipt.effectiveGasPrice,
            "submit_ms": (submitted-start)*1000, "receipt_wait_ms": (confirmed-submitted)*1000,
            "confirmation_ms": (confirmed-start)*1000, "event_decode_ms": 0.0}
        self.transactions.append(sample)
        return receipt

    def event(self, contract, name, receipt):
        start = time.perf_counter()
        events = getattr(contract.events,name)().process_receipt(receipt,errors=DISCARD)
        elapsed = (time.perf_counter()-start)*1000
        self.transactions[-1]["event_decode_ms"] = elapsed
        if len(events) != 1:
            raise RuntimeError("Expected one " + name + " event")
        return events[0]["args"]

    def deploy(self, name, *args):
        path = ROOT / "artifacts/contracts" / (name + ".sol") / (name + ".json")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        factory = self.w3.eth.contract(abi=artifact["abi"],bytecode=artifact["bytecode"])
        receipt = self.send(factory.constructor(*args),self.admin,"deploy_" + name)
        return self.w3.eth.contract(address=receipt.contractAddress,abi=artifact["abi"])

    def patient(self, index):
        address = Web3.to_checksum_address("0x" + hashlib.sha256(("P4 synthetic patient " + str(index)).encode()).hexdigest()[-40:])
        for method, params in (("hardhat_setBalance",[address,hex(Web3.to_wei(10,"ether"))]),
                               ("hardhat_impersonateAccount",[address])):
            result = self.w3.provider.make_request(method,params)
            if "error" in result:
                raise RuntimeError(str(result["error"]))
        return address

    def run(self):
        start = time.perf_counter()
        registry = self.deploy("HealthRegistry",self.admin)
        reward = self.deploy("ConsentReward",registry.address,self.admin)
        manager = self.deploy("ConsentManager",registry.address,reward.address)
        self.send(reward.functions.setConsentManager(manager.address),self.admin,"set_manager")
        for doctor in (self.doctor,self.otherDoctor):
            identityHash = hashlib.sha256(("synthetic doctor " + doctor).encode()).digest()
            self.send(registry.functions.registerUser(identityHash,2),doctor,"register_doctor")
            self.send(registry.functions.setVerification(doctor,True),self.admin,"verify_doctor")

        for index in range(self.patients):
            patient = self.patient(index)
            identityHash = hashlib.sha256(("synthetic patient and salt " + str(index)).encode()).digest()
            self.send(registry.functions.registerUser(identityHash,1),patient,"register_patient")
            self.send(registry.functions.setVerification(patient,True),self.admin,"verify_patient")

            data = self.folder / ("patient-" + str(index))
            data.mkdir()
            record = {"synthetic": True, "patient_ref": "patient-" + str(index), "record_type": "blood test panel", "results": [{"test": "demo", "value": index, "unit": "synthetic"}]}
            (data / "fake-record.json").write_text(json.dumps(record),encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                fileHash = encrypt_record_file(str(data / "fake-record.json"),str(data / "fake-record.enc"),str(data / "secret.key"))
            receipt = self.send(registry.functions.registerRecord(bytes.fromhex(fileHash[2:]),"blood test panel"),patient,"register_record")
            recordId = self.event(registry,"RecordRegistered",receipt)["recordId"]

            receipt = self.send(manager.functions.requestAccess(recordId,0),self.otherDoctor,"request_denied_no_consent")
            if self.event(manager,"AccessDecision",receipt)["allowed"]:
                raise AssertionError("Unconsented doctor was allowed")

            receipt = self.send(manager.functions.grantAccess(recordId,"blood test panel",self.doctor,7),patient,"grant_rewarded")
            grantId = self.event(manager,"ConsentGranted",receipt)["grantId"]
            receipt = self.send(manager.functions.requestAccess(recordId,grantId),self.doctor,"request_allowed")
            decision = self.event(manager,"AccessDecision",receipt)
            if not decision["allowed"]:
                raise AssertionError("Consented doctor was denied")

            requestId = str(decision["requestId"])
            service = MedicalDataDeliveryService(self.w3,registry.address,registry.abi,manager.address,manager.abi,
                data_dir=str(self.folder),db_path=str(self.folder / "service_state.db"))
            service.register_record_file(recordId,str(data / "fake-record.enc"),str(data / "secret.key"))
            challenge = service.issue_delivery_challenge(recordId,self.doctor,Web3.to_hex(receipt.transactionHash),requestId)
            signature = Web3.to_hex(self.w3.eth.sign(self.doctor,text=challenge))
            authStart = time.perf_counter()
            service.verify_requester_identity(self.doctor,signature,challenge)
            authMs = (time.perf_counter()-authStart)*1000
            permissionStart = time.perf_counter()
            active = manager.functions.checkPermission(grantId,self.doctor,recordId).call()
            permissionMs = (time.perf_counter()-permissionStart)*1000
            if not active:
                raise AssertionError("Current consent lookup denied")
            deliveryStart = time.perf_counter()
            delivered = service.request_record_delivery(recordId,self.doctor,signature,challenge,Web3.to_hex(receipt.transactionHash),requestId)
            deliveryMs = (time.perf_counter()-deliveryStart)*1000
            if delivered != record or not service.db.is_consumed(requestId):
                raise AssertionError("Delivery or persistent consumption mismatch")
            self.deliveries.append({"patients": self.patients, "repetition": self.repetition,
                "patient": patient, "record_id": recordId, "request_id": requestId,
                "authentication_ms": authMs, "permission_lookup_ms": permissionMs, "delivery_total_ms": deliveryMs})

            receipt = self.send(manager.functions.revokeAccess(recordId,grantId),patient,"revoke")
            self.event(manager,"ConsentRevoked",receipt)
            receipt = self.send(manager.functions.requestAccess(recordId,grantId),self.doctor,"request_denied_revoked")
            if self.event(manager,"AccessDecision",receipt)["allowed"]:
                raise AssertionError("Revoked doctor was allowed")
            self.send(manager.functions.grantAccess(recordId,"blood test panel",self.doctor,7),patient,"grant_renewal")
            if reward.functions.balanceOf(patient).call() != 10:
                raise AssertionError("Renewal rewarded twice")

        return {"patients": self.patients, "repetition": self.repetition, "requesters": 2, "administrators": 1,
            "transactions": len(self.transactions), "deliveries": len(self.deliveries), "failures": 0,
            "total_gas": sum(row["gas_used"] for row in self.transactions),
            "local_fee_wei": sum(row["fee_wei"] for row in self.transactions), "elapsed_s": time.perf_counter()-start}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--users",type=int,nargs="+",default=[5,20,50])
    parser.add_argument("--repetitions",type=int,default=3)
    args = parser.parse_args()
    if min(args.users) < 1 or args.repetitions < 1:
        parser.error("users and repetitions must be positive")
    runId = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / "results/p4-evaluation" / runId
    folder.mkdir(parents=True)
    metadata = environment()
    metadata.update({"patients": args.users, "repetitions": args.repetitions,
        "environment": "temporary local Hardhat node; auto-mining; no public network",
        "reset": "evm_revert to initial node snapshot before every workload; fresh private directories and database",
        "routing": "benchmark registers each ciphertext/key with the service's persistent chain/registry/record mapping; signs server-issued challenges",
        "timing": "confirmation includes transaction submission and receipt lookup; event parsing separate; authentication and permission probes separate; delivery_total includes the service's own authentication and chain checks, so these columns are not additive"})
    transactions, deliveries, workloads = [], [], []
    try:
        OffchainServiceTest.setUpClass()
        w3 = OffchainServiceTest.w3
        snapshot = w3.provider.make_request("evm_snapshot",[])["result"]
        with tempfile.TemporaryDirectory(prefix="p4-evaluation-") as temporary:
            for patients in args.users:
                for repetition in range(1,args.repetitions + 1):
                    reset = w3.provider.make_request("evm_revert",[snapshot])
                    if reset.get("result") is not True:
                        raise RuntimeError("Snapshot reset failed")
                    snapshot = w3.provider.make_request("evm_snapshot",[])["result"]
                    data = Path(temporary) / (str(patients) + "-" + str(repetition))
                    data.mkdir()
                    run = Workload(w3,patients,repetition,data)
                    workloadStart = time.perf_counter()
                    try:
                        workloads.append(run.run())
                        print("Completed",patients,"patients, run",repetition,flush=True)
                    except Exception as failure:
                        workloads.append({"patients": patients, "repetition": repetition,
                            "transactions": len(run.transactions), "deliveries": len(run.deliveries), "failures": 1,
                            "total_gas": sum(row["gas_used"] for row in run.transactions),
                            "elapsed_s": time.perf_counter()-workloadStart, "error": repr(failure)})
                        print("Failed",patients,"patients, run",repetition,repr(failure),flush=True)
                    finally:
                        transactions.extend(run.transactions)
                        deliveries.extend(run.deliveries)
                        (folder / ("receipts-" + str(patients) + "-" + str(repetition) + ".json")).write_text(
                            json.dumps(run.receipts,indent=2) + "\n",encoding="utf-8")
    finally:
        OffchainServiceTest.doClassCleanups()
        saveCsv(folder / "transactions.csv",transactions)
        saveCsv(folder / "deliveries.csv",deliveries)
        saveCsv(folder / "workloads.csv",workloads)
        (folder / "run.json").write_text(json.dumps(metadata,indent=2) + "\n",encoding="utf-8")

    if any(row["failures"] for row in workloads):
        print("Workload failure: partial raw evidence preserved; no complete-run averages published.")
        return 1
    gasSummary = []
    for operation in sorted({row["operation"] for row in transactions}):
        rows = [row for row in transactions if row["operation"] == operation]
        gasSummary.append({"operation": operation, "samples": len(rows),
            "average_gas": statistics.mean(row["gas_used"] for row in rows),
            "min_gas": min(row["gas_used"] for row in rows), "max_gas": max(row["gas_used"] for row in rows),
            "average_confirmation_ms": statistics.mean(row["confirmation_ms"] for row in rows),
            "average_event_decode_ms": statistics.mean(row["event_decode_ms"] for row in rows)})
    scaling = []
    for patients in args.users:
        rows = [row for row in workloads if row["patients"] == patients]
        releases = [row for row in deliveries if row["patients"] == patients]
        scaling.append({"patients": patients, "repetitions": len(rows), "transactions_per_run": rows[0]["transactions"],
            "deliveries_per_run": rows[0]["deliveries"], "average_total_gas": statistics.mean(row["total_gas"] for row in rows),
            "average_elapsed_s": statistics.mean(row["elapsed_s"] for row in rows),
            "average_authentication_ms": statistics.mean(row["authentication_ms"] for row in releases),
            "average_permission_lookup_ms": statistics.mean(row["permission_lookup_ms"] for row in releases),
            "average_delivery_total_ms": statistics.mean(row["delivery_total_ms"] for row in releases),
            "failures": sum(row["failures"] for row in rows)})
    saveCsv(folder / "gas-summary.csv",gasSummary)
    saveCsv(folder / "scaling-summary.csv",scaling)
    (folder.parent / "latest.json").write_text(json.dumps({"folder": str(folder.relative_to(ROOT)).replace("\\","/")},indent=2) + "\n",encoding="utf-8")
    print("Evidence:",folder)
    return 1 if any(row["failures"] for row in workloads) else 0


if __name__ == "__main__":
    raise SystemExit(main())
