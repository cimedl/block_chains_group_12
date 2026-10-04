import os
import json
import secrets
from datetime import datetime, timezone
from cryptography.fernet import Fernet

from crypto_utils import calculate_file_hash

KEY_PATH = os.path.join("data", "secret.key")
PLAINTEXT_RECORD_PATH = os.path.join("data", "fake-record.json")
ENCRYPTED_RECORD_PATH = os.path.join("data", "fake-record.enc")

def get_or_create_key(key_path: str = KEY_PATH) -> bytes:
    # Load key，or generate a new one
    # Use for local file encryption and decryption
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    if os.path.exists(key_path):
        with open(key_path, "rb") as kf:
            return kf.read()
    
    key = Fernet.generate_key()
    with open(key_path, "wb") as kf:
        kf.write(key)
    print(f"Generate a new key and save it to: {key_path}")
    return key

def encrypt_record_file(
    input_json_path: str = PLAINTEXT_RECORD_PATH,
    output_enc_path: str = ENCRYPTED_RECORD_PATH,
    key_path: str = KEY_PATH
) -> str:
    # Read Json file, use fernt to encrypted
    # Return the 32-byte on-chain recordHash
    key = get_or_create_key(key_path)
    cipher = Fernet(key)

    with open(input_json_path, "rb") as f:
        plaintext_bytes = f.read()

    encrypted_bytes = cipher.encrypt(plaintext_bytes)

    # Write encrypted output
    with open(output_enc_path, "wb") as f:
        f.write(encrypted_bytes)
    print(f"Encrypted output path: {output_enc_path}")

    onchain_record_hash = calculate_file_hash(encrypted_bytes)
    return onchain_record_hash

def decrypt_record_file(
    enc_path: str = ENCRYPTED_RECORD_PATH,
    key_path: str = KEY_PATH
) -> dict:
    # Reads and decrypts the ciphertext file, returning the original data (for delivery)
    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"File doen't exist: {enc_path}")

    with open(enc_path, "rb") as f:
        encrypted_bytes = f.read()
    return decrypt_record_bytes(encrypted_bytes, key_path)


def decrypt_record_bytes(encrypted_bytes: bytes, key_path: str = KEY_PATH) -> dict:
    with open(key_path, "rb") as kf:
        key = kf.read()
    decrypted_bytes = Fernet(key).decrypt(encrypted_bytes)
    return json.loads(decrypted_bytes.decode("utf-8"))


# if __name__ == "__main__":
#     record_hash = encrypt_record_file()
#     print(f"Generated on-chain recordHash: {record_hash}")