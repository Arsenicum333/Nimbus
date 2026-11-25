import struct
from typing import Dict, Any, Tuple, Optional

from utils.checksum import compute_checksum
from utils.sensorPayload import PAYLOAD_SIZES, pack_sensor_data, unpack_sensor_data
from enums.packetType import PacketType

def pack_registration(sensor_id: int, timestamp: int, low_battery: bool) -> bytes:
    header_byte = (PacketType.REGISTRATION.value << 5) | (sensor_id << 3) | (int(low_battery) << 2)
    header = struct.pack('>B I', header_byte, timestamp)
    checksum = compute_checksum(header)
    return header + struct.pack('>I', checksum)

def unpack_registration(data: bytes) -> Optional[Tuple[int, int, bool]]:
    if len(data) != 9:
        return None

    header = data[:5]
    received_checksum = struct.unpack('>I', data[5:9])[0]

    if compute_checksum(header) != received_checksum:
        return None

    first_byte, timestamp = struct.unpack('>B I', header)
    packet_type = (first_byte >> 5) & 0x7
    if packet_type != PacketType.REGISTRATION.value:
        return None

    sensor_id = (first_byte >> 3) & 0x3
    low_battery = bool((first_byte >> 2) & 0x1)

    return sensor_id, timestamp, low_battery

def pack_data(sensor_id: int, token: int, timestamp: int, low_battery: bool,
              sensor_data: Dict[str, Any]) -> bytes:
    header_byte = (PacketType.DATA.value << 5) | (sensor_id << 3) | (int(low_battery) << 2)
    header = struct.pack('>B I I', header_byte, token, timestamp)

    data_bytes = pack_sensor_data(sensor_id, sensor_data)
    checksum_data = header + data_bytes
    checksum = compute_checksum(checksum_data)

    return checksum_data + struct.pack('>I', checksum)

def unpack_data(data: bytes) -> Optional[Tuple[int, int, int, bool, Dict[str, Any]]]:
    if not data:
        return None

    first_byte = data[0]
    packet_type = (first_byte >> 5) & 0x7
    if packet_type != PacketType.DATA.value:
        return None

    sensor_id = (first_byte >> 3) & 0x3
    data_size = PAYLOAD_SIZES[sensor_id]

    # header (type byte + token + timestamp) + payload + checksum
    if len(data) != 9 + data_size + 4:
        return None

    header = data[:9]
    sensor_data_bytes = data[9:9+data_size]
    received_checksum = struct.unpack('>I', data[9+data_size:9+data_size+4])[0]

    if compute_checksum(header + sensor_data_bytes) != received_checksum:
        return None

    first_byte, token, timestamp = struct.unpack('>B I I', header)
    sensor_id = (first_byte >> 3) & 0x3
    low_battery = bool((first_byte >> 2) & 0x1)

    sensor_data = unpack_sensor_data(sensor_id, sensor_data_bytes)

    return sensor_id, token, timestamp, low_battery, sensor_data

def pack_activity_confirmation(sensor_id: int, token: int, timestamp: int, low_battery: bool) -> bytes:
    header_byte = (PacketType.ACTIVITY_CONFIRMATION.value << 5) | (sensor_id << 3) | (int(low_battery) << 2)
    header = struct.pack('>B I I', header_byte, token, timestamp)
    checksum = compute_checksum(header)
    return header + struct.pack('>I', checksum)

def unpack_activity_confirmation(data: bytes) -> Optional[Tuple[int, int, int, bool]]:
    if len(data) != 13:
        return None

    header = data[:9]
    received_checksum = struct.unpack('>I', data[9:13])[0]

    if compute_checksum(header) != received_checksum:
        return None

    first_byte, token, timestamp = struct.unpack('>B I I', header)
    packet_type = (first_byte >> 5) & 0x7
    if packet_type != PacketType.ACTIVITY_CONFIRMATION.value:
        return None

    sensor_id = (first_byte >> 3) & 0x3
    low_battery = bool((first_byte >> 2) & 0x1)

    return sensor_id, token, timestamp, low_battery

def pack_registration_response(sensor_id: int, token: int, timestamp: int) -> bytes:
    header_byte = (PacketType.REGISTRATION_RESPONSE.value << 5) | (sensor_id << 3)
    header = struct.pack('>B I I', header_byte, token, timestamp)
    checksum = compute_checksum(header)
    return header + struct.pack('>I', checksum)

def unpack_registration_response(data: bytes) -> Optional[Tuple[int, int, int]]:
    if len(data) != 13:
        return None

    header = data[:9]
    received_checksum = struct.unpack('>I', data[9:13])[0]

    if compute_checksum(header) != received_checksum:
        return None

    first_byte, token, timestamp = struct.unpack('>B I I', header)
    packet_type = (first_byte >> 5) & 0x7
    if packet_type != PacketType.REGISTRATION_RESPONSE.value:
        return None

    sensor_id = (first_byte >> 3) & 0x3

    return sensor_id, token, timestamp

def pack_server_packet(packet_type: PacketType, sensor_id: int, timestamp: int) -> bytes:
    header_byte = (packet_type.value << 5) | (sensor_id << 3)
    header = struct.pack('>B I', header_byte, timestamp)
    checksum = compute_checksum(header)
    return header + struct.pack('>I', checksum)

def unpack_server_packet(data: bytes) -> Optional[Tuple[PacketType, int, int]]:
    if len(data) != 9:
        return None

    header = data[:5]
    received_checksum = struct.unpack('>I', data[5:9])[0]

    if compute_checksum(header) != received_checksum:
        return None

    first_byte, timestamp = struct.unpack('>B I', header)
    packet_type_num = (first_byte >> 5) & 0x7

    try:
        packet_type = PacketType(packet_type_num)
    except ValueError:
        return None

    sensor_id = (first_byte >> 3) & 0x3

    return packet_type, sensor_id, timestamp

def send_binary(sock, data: bytes, addr):
    sock.sendto(data, addr)

def parse_binary_packet(data: bytes):
    if not data:
        return None

    if len(data) > 0:
        first_byte = data[0]
        packet_type_num = (first_byte >> 5) & 0x7

        try:
            packet_type = PacketType(packet_type_num)
        except ValueError:
            return None

        if packet_type == PacketType.REGISTRATION and len(data) == 9:
            result = unpack_registration(data)
            if result:
                return ('REGISTRATION', result)

        elif packet_type == PacketType.DATA:
            result = unpack_data(data)
            if result:
                return ('DATA', result)

        elif packet_type == PacketType.ACTIVITY_CONFIRMATION and len(data) == 13:
            result = unpack_activity_confirmation(data)
            if result:
                return ('ACTIVITY_CONFIRMATION', result)

        elif packet_type == PacketType.REGISTRATION_RESPONSE and len(data) == 13:
            result = unpack_registration_response(data)
            if result:
                return ('REGISTRATION_RESPONSE', result)

        elif packet_type in [PacketType.DATA_RECEIVED, PacketType.REQUEST_RESEND,
                           PacketType.INVALID_TOKEN, PacketType.ACTIVITY_CHECK] and len(data) == 9:
            result = unpack_server_packet(data)
            if result:
                packet_type_enum, sensor_id, timestamp = result
                return (packet_type_enum.name, (sensor_id, timestamp))

    return None
