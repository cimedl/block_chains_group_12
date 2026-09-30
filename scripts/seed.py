# seed.py

# create the starting demo data

from web3 import Web3

def load_deployment():
    # Read addresses produced by deploy.py
    pass

def get_accounts(w3):
    # Get Alice, Bob, Carol, etc.
    pass

def register_users(contract, accounts):
    # Register demo identities
    pass

def create_records():
    # Create synthetic medical JSON files
    pass

def publish_records(contract, records):
    # Store record information/hash on-chain
    pass

def main():
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

    deployment = load_deployment()
    accounts = get_accounts(w3)

    register_users(deployment["health_registry"], accounts)

    records = create_records()

    publish_records(
        deployment["health_registry"],
        records
    )

if __name__ == "__main__":
    main()