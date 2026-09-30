import os
import json
import hashlib
from eth_account import Account
from eth_account.messages import encode_defunct
from cryptography.fernet import Fernet

# Signature Verification
# Integrity Check
# Replay Prevention
# Decryption

CONSUMED_REQUESTS = set()

# Request payload sent by requester
def deliver_record(
    requester_address: str, signature: str, challenge_message: str, ticket_id: str, expected_record_hash: str ):
    if ticket_id in CONSUMED_REQUESTS:
        return {"success": False, "error": "Ticket already used!"}

    # Check Signature
    try:
        signable_message = encode_defunct(text=challenge_message)
        recovered_address = Account.recover_message(signable_message, signature=signature)
        if recovered_address.lower() != requester_address.lower():
            return {"success": False, "error": "Signature does not match your wallet address!"}
    except Exception as e:
        return {"success": False, "error": f"Invalid signature format: {str(e)}"}

    # Load Local Encrypted Record and Key
    encrypted_path = os.path.join("data", "fake-record.enc")
    key_path = os.path.join("data", "secret.key")

    if not os.path.exists(encrypted_path) or not os.path.exists(key_path):
        return {"success": False, "error": "Encrypted file or secret key missing on disk."}

    with open(encrypted_path, "rb") as f:
        encrypted_bytes = f.read()

    # Integrity Check
    # Compare local file hash against expected on-chain hash
    local_hash = "0x" + hashlib.sha256(encrypted_bytes).hexdigest()
    if local_hash.lower() != expected_record_hash.lower():
        return {"success": False, "error": "File tampered! Hash mismatch."}

    # Consume Ticket
    # Prevent future reuse
    CONSUMED_REQUESTS.add(ticket_id)

    # Decrypt and release data
    with open(key_path, "rb") as kf:
        key = kf.read()

    cipher = Fernet(key)
    decrypted_bytes = cipher.decrypt(encrypted_bytes)
    record_data = json.loads(decrypted_bytes.decode("utf-8"))

    return {
        "success": True,
        "verified_hash": local_hash,
        "data": record_data
    }

# Test
if __name__ == "__main__":
    print("Testing\n")

    # Create a test doctor
    doctor_wallet = Account.create()
    doctor_address = doctor_wallet.address
    challenge = "Doctor access request #001"
    signature = doctor_wallet.sign_message(encode_defunct(text=challenge)).signature.hex()

    # Read current encrypted file's hash as expected hash
    with open("data/fake-record.enc", "rb") as f:
        valid_hash = "0x" + hashlib.sha256(f.read()).hexdigest()

    # Try to deliver record
    result = deliver_record(
        requester_address=doctor_address,
        signature=signature,
        challenge_message=challenge,
        ticket_id="TICKET-001",
        expected_record_hash=valid_hash
    )

    print("Delivery Result:")
    print(f"Success: {result['success']}")
    if result["success"]:
        print(f"Record Type: {result['data'].get('record_type')}")
        print(f"Patient Name: {result['data'].get('results')}")