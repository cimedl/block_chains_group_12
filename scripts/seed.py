# seed.py

# create the starting demo data

from web3 import Web3
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_FILE = ROOT / ".local" / "deployment.json"
DATA_DIR = ROOT / "data"

w3 = None

def load_deployment():
    # Read addresses produced by deploy.py
    if not DEPLOYMENT_FILE.exists():
        raise FileNotFoundError(
        f"Deployment file not found: {DEPLOYMENT_FILE}\n" "Run deploy.js first."
        )
    with open(DEPLOYMENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_contract(w3, contract_name, contract_address):

    artifact_path = (ROOT / "artifacts" / "contracts" / f"{contract_name}.sol" / f"{contract_name}.json")
    if not artifact_path.exists():
        raise FileNotFoundError(
        f"Artifact not found: {artifact_path}\n" "Run Hardhat compile first."
    )
    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    return w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=artifact["abi"], )

def get_accounts(w3):
    # Get Alice, Bob, Carol, etc.
    accounts = w3.eth.accounts
    if len(accounts) < 4:
        raise RuntimeError("Need at least 4 Hardhat accounts " "(admin, Alice, Bob, Carol).")
    return {"admin": accounts[0], "alice": accounts[1], "bob": accounts[2], "carol": accounts[3], }

def send_transaction(tx_function, sender):
    # Send a transaction using an unlocked Hardhat account
    transaction = tx_function.build_transaction({ "from": sender, "nonce": w3.eth.get_transaction_count(sender),
                                                  "gas": 500_000, "gasPrice": w3.eth.gas_price, })
    tx_hash = w3.eth.send_transaction(transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction failed: {tx_hash.hex()}")
    return receipt

def identity_hash(name):
    # Create a deterministic synthetic identity hash
    return hashlib.sha256( f"demo-identity:{name}".encode("utf-8") ).digest()

def register_users(contract, accounts):
    # register demo identities
    users = [
        ("Alice", accounts["alice"], 1),
        ("Bob", accounts["bob"], 1),
        ("Carol", accounts["carol"], 2),
    ]

    print("Registering demo users...")

    for name, account, role in users:
        identity = identity_hash(name)

        send_transaction(
            contract.functions.registerUser(
                identity,
                role,
            ),
            account,
        )

        print(f"Registered {name}: {account}")

    print("Verifying demo users...")

    for name, account, _role in users:
        send_transaction(
            contract.functions.setVerification(
                account,
                True,
            ),
            accounts["admin"],
        )

        print(f"Verified {name}")

def hash_file(path):
    # Calculate SHA-256 of a local file
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).digest()

def create_records(accounts):
    # Create synthetic medical JSON files

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    alice_record = {
        "patient": "Alice",
        "record_type": "LAB_REPORT",
        "record_id": "alice-demo-001",
        "test": "Synthetic Blood Test",
        "result": "Normal",
        "notes": "Fictional data for blockchain demonstration.",
    }

    bob_record = {
        "patient": "Bob",
        "record_type": "LAB_REPORT",
        "record_id": "bob-demo-001",
        "test": "Synthetic Cholesterol Test",
        "result": "Within fictional reference range",
        "notes": "Fictional data for blockchain demonstration.",
    }

    files = [
        (accounts["alice"], DATA_DIR / "alice_lab.json", alice_record),
        (accounts["bob"], DATA_DIR / "bob_lab.json", bob_record),
    ]

    records = []

    for patient, path, data in files:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

        records.append({
            "patient": patient,
            "path": path,
            "record_type": data["record_type"],
            "hash": hash_file(path),
        })

        print(f"Created {path}")

    return records

def publish_records(contract, records):
    # Store record information/hash on-chain
    results = []

    for record in records:
        receipt = send_transaction(
            contract.functions.registerRecord(
                record["hash"],
                record["record_type"],
            ),
            record["patient"],
        )

        events = contract.events.RecordRegistered().process_receipt(receipt)

        if not events:
            raise RuntimeError("Could not find RecordRegistered event.")

        record_id = events[0]["args"]["recordId"]

        result = dict(record)
        result["record_id"] = record_id
        results.append(result)

        print(f"Published record {record_id} for {record['path']}")

    return results

def main():
    global w3
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    if not w3.is_connected():
        raise RuntimeError("Could not connect to local Hardhat node.")

    deployment = load_deployment()
    accounts = get_accounts(w3)
    registry_address = deployment["contracts"]["HealthRegistry"]["address"]
    health_registry = load_contract(w3, "HealthRegistry", registry_address, )

    print("\n---REGISTERING USERS---")
    register_users(health_registry, accounts)

    print("\n---CREATING FILES---")
    records = create_records(accounts)

    print("\n---PUBLISHING RECORDS---")
    records = publish_records(health_registry,
                              records, )  # Save the generated record information so demo.py
                                          # knows which record ID belongs to Alice's file.

    seed_output = DATA_DIR / "seed.json"
    serializable_records = []

    for record in records:
        serializable_records.append({ "patient": record["patient"], "path": str(record["path"]), "record_type": record["record_type"], "hash": "0x" + record["hash"].hex(), "record_id": record["record_id"], })
        with open(seed_output, "w", encoding="utf-8") as f:
            json.dump( serializable_records, f, indent=2, )
            f.write("\n")

    print("\n---SEED CREATED---")
    print(f"Created {len(records)} records.")
    print(f"Seed information: {seed_output}")

if __name__ == "__main__":
    main()