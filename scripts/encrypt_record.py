import hashlib
import json
import os
from cryptography.fernet import Fernet

def run_encryption():

    input_path = os.path.join("data", "fake-record.json")
    output_path = os.path.join("data", "fake-record.enc")
    key_path = os.path.join("data", "secret.key")

    # check is the path exit
    if not os.path.exists(input_path):
        print(f"[-] error: cannot find input {input_path}")
        return

    # read data
    with open(input_path, "r", encoding="utf-8") as f:
        plaintext_data = f.read()

    # Generate or load a symmetric key, used for decryption
    # To ensure the same key can be used for decryption, generate and save it locally if it does not already exist.
    if os.path.exists(key_path):
        with open(key_path, "rb") as kf:
            key = kf.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as kf:
            kf.write(key)
        print(f"Key path: {key_path}")

    cipher = Fernet(key)

    encrypted_bytes = cipher.encrypt(plaintext_data.encode("utf-8"))

    # Write encrypted output to local
    with open(output_path, "wb") as f:
        f.write(encrypted_bytes)
    print(f"Encrypted output path: {output_path}")

    #Hash with SHA-256 （add 0x）
    sha256_hash = hashlib.sha256(encrypted_bytes).hexdigest()
    onchain_record_hash = "0x" + sha256_hash

    print("=")
    print(f"The recordHash provided the registerRecord() is:")
    print(onchain_record_hash)


if __name__ == "__main__":
    run_encryption()