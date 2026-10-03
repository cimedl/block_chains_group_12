# TODO: review all code in this file imported from part3.
import hashlib
import json
from typing import Union, Dict, Any


# TODO: review this imported or added definition.
def ensure_bytes32(value: bytes | str) -> bytes:
    # Normalize hex string or bytes to a standard 32-byte representation.
    if isinstance(value, str):
        cleaned = value[2:] if value.startswith("0x") else value
        try:
            value_bytes = bytes.fromhex(cleaned)
        except ValueError as e:
            raise ValueError(f"Invalid hex string: {e}")
    elif isinstance(value, (bytes, bytearray)):
        value_bytes = bytes(value)
    else:
        raise TypeError(f"Expected bytes or hex str, got {type(value)}")

    if len(value_bytes) != 32:
        raise ValueError(f"Expected 32-byte value, got {len(value_bytes)} bytes")
    return value_bytes

# TODO: review this imported or added definition.
def to_hex32(value: Union[bytes, str]) -> str:
    raw_bytes = ensure_bytes32(value)
    return "0x" + raw_bytes.hex().lower()

# TODO: review this imported or added definition.
def calculate_sha256(data: bytes) -> bytes:
    #Calculate the 32-byte SHA-256 of binary data
    return hashlib.sha256(data).digest()

# TODO: review this imported or added definition.
def calculate_json_hash(json_obj: Dict[str, Any]) -> str:
    serialized = json.dumps(
        json_obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True
    ).encode("utf-8")
    
    digest = calculate_sha256(serialized)
    return "0x" + digest.hex().lower()

# TODO: review this imported or added definition.
def calculate_file_hash(file_bytes: bytes) -> str:
    digest = calculate_sha256(file_bytes)
    return "0x" + digest.hex().lower()