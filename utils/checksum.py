import json
import zlib

def compute_checksum(data: dict) -> int:
    data_without_checksum = {key: value for key, value in data.items() if key != "checksum"}
    data_without_checksum = serialization_to_json(data_without_checksum)

    json_string = json.dumps(
        data_without_checksum,
        sort_keys=True,
        separators=(",", ":")
    )

    json_bytes = json_string.encode("utf-8")

    return zlib.crc32(json_bytes) & 0xFFFFFFFF

def serialization_to_json(obj):
    if isinstance(obj, dict):
        return {key: serialization_to_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialization_to_json(value) for value in obj]
    elif hasattr(obj, "value"): # For Enum
        return obj.value
    else:
        return obj
