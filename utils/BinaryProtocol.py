import struct
from typing import Dict, Any, Tuple, Optional

from utils.Checksum import compute_checksum
from enums.PacketType import PacketType

def pack_sensor_data(sensor_id: int, data: Dict[str, Any]) -> bytes:
    if sensor_id == 0:
        temperature = int((data['temperature'] + 50.0) * 10)
        humidity = int(data['humidity'] * 10)
        dew_point = int((data['dew_point'] + 50.0) * 10)
        pressure = int(data['pressure'] * 100) - 80000

        packed = (temperature & 0x7FF) | ((humidity & 0x3FF) << 11) | \
                ((dew_point & 0x7FF) << 21) | ((pressure & 0x7FFF) << 32)
        return struct.pack('>Q', packed)[2:8]

    elif sensor_id == 1:
        wind_speed = int(data['wind_speed'] * 10)
        wind_gust = int(data['wind_gust'] * 10)
        wind_direction = data['wind_direction']
        turbulence = int(data['turbulence'] * 10)

        packed = (wind_speed & 0x1FF) | ((wind_gust & 0x3FF) << 9) | \
                ((wind_direction & 0x1FF) << 19) | ((turbulence & 0xF) << 28)
        return struct.pack('>I', packed)

    elif sensor_id == 2:
        rainfall = int(data['rainfall'] * 10)
        soil_moisture = int(data['soil_moisture'] * 10)
        flood_risk = data['flood_risk']
        rain_duration = data['rain_duration']

        packed = (rainfall & 0x1FFF) | ((soil_moisture & 0x3FF) << 13) | \
                ((flood_risk & 0x3) << 23) | ((rain_duration & 0x3F) << 25)
        return struct.pack('>I', packed)

    elif sensor_id == 3:
        co2 = data['co2'] - 300
        ozone = int(data['ozone'] * 10)
        aqi = data['air_quality_index']

        packed = (co2 & 0x1FFF) | ((ozone & 0x1FFF) << 13) | \
                ((aqi & 0x1FF) << 26)
        return struct.pack('>Q', packed)[3:8]

    return b''

def unpack_sensor_data(sensor_id: int, data: bytes) -> Dict[str, Any]:
    result = {}

    if sensor_id == 0 and len(data) >= 6:
        packed = struct.unpack('>Q', b'\x00\x00' + data[:6])[0]
        temperature = ((packed & 0x7FF) / 10.0) - 50.0
        humidity = ((packed >> 11) & 0x3FF) / 10.0
        dew_point = ((packed >> 21) & 0x7FF) / 10.0 - 50.0
        pressure = ((packed >> 32) & 0x7FFF) / 100.0 + 800.0

        result.update({
            'temperature': round(temperature, 1),
            'humidity': round(humidity, 1),
            'dew_point': round(dew_point, 1),
            'pressure': round(pressure, 2)
        })

    elif sensor_id == 1 and len(data) >= 4:
        packed = struct.unpack('>I', data[:4])[0]
        wind_speed = ((packed & 0x1FF) / 10.0)
        wind_gust = ((packed >> 9) & 0x3FF) / 10.0
        wind_direction = (packed >> 19) & 0x1FF
        turbulence = ((packed >> 28) & 0xF) / 10.0

        result.update({
            'wind_speed': round(wind_speed, 1),
            'wind_gust': round(wind_gust, 1),
            'wind_direction': wind_direction,
            'turbulence': round(turbulence, 1)
        })

    elif sensor_id == 2 and len(data) >= 4:
        packed = struct.unpack('>I', data[:4])[0]
        rainfall = ((packed & 0x1FFF) / 10.0)
        soil_moisture = ((packed >> 13) & 0x3FF) / 10.0
        flood_risk = (packed >> 23) & 0x3
        rain_duration = (packed >> 25) & 0x3F

        result.update({
            'rainfall': round(rainfall, 1),
            'soil_moisture': round(soil_moisture, 1),
            'flood_risk': flood_risk,
            'rain_duration': rain_duration
        })

    elif sensor_id == 3 and len(data) >= 5:
        packed = struct.unpack('>Q', b'\x00\x00\x00' + data[:5])[0]
        co2 = (packed & 0x1FFF) + 300
        ozone = ((packed >> 13) & 0x1FFF) / 10.0
        aqi = (packed >> 26) & 0x1FF

        result.update({
            'co2': co2,
            'ozone': round(ozone, 1),
            'air_quality_index': aqi
        })

    return result

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
    if len(data) < 17:
        return None

    first_byte = data[0]
    packet_type = (first_byte >> 5) & 0x7
    if packet_type != PacketType.DATA.value:
        return None

    sensor_id = (first_byte >> 3) & 0x3

    if sensor_id == 0:
        expected_size = 19
    elif sensor_id == 3:
        expected_size = 18
    else:
        expected_size = 17

    if len(data) != expected_size:
        return None

    data_size = 6 if sensor_id == 0 else (5 if sensor_id == 3 else 4)

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

        elif packet_type == PacketType.DATA and len(data) in [17, 18, 19]:
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
