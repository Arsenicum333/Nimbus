import struct
from typing import Dict, Any

# Bit-packed measurement values of each sensor (payload of the DATA packet).
# Every value is stored as an unsigned integer offset from its minimum and scaled
# by its precision, using only as many bits as its range requires.

# Payload size in bytes for each sensor ID
PAYLOAD_SIZES = {
    0: 6,  # ThermoNode:    11 + 10 + 11 + 15 = 47 bits
    1: 4,  # WindSense:      9 + 10 +  9 +  4 = 32 bits
    2: 4,  # RainDetect:    13 + 10 +  2 +  6 = 31 bits
    3: 5,  # AirQualityBox: 13 + 13 +  9      = 35 bits
}

def pack_sensor_data(sensor_id: int, data: Dict[str, Any]) -> bytes:
    if sensor_id == 0:
        temperature = round((data['temperature'] + 50.0) * 10)
        humidity = round(data['humidity'] * 10)
        dew_point = round((data['dew_point'] + 50.0) * 10)
        pressure = round(data['pressure'] * 100) - 80000

        packed = (temperature & 0x7FF) | ((humidity & 0x3FF) << 11) | \
                ((dew_point & 0x7FF) << 21) | ((pressure & 0x7FFF) << 32)
        return struct.pack('>Q', packed)[2:8]

    elif sensor_id == 1:
        wind_speed = round(data['wind_speed'] * 10)
        wind_gust = round(data['wind_gust'] * 10)
        wind_direction = data['wind_direction']
        turbulence = round(data['turbulence'] * 10)

        packed = (wind_speed & 0x1FF) | ((wind_gust & 0x3FF) << 9) | \
                ((wind_direction & 0x1FF) << 19) | ((turbulence & 0xF) << 28)
        return struct.pack('>I', packed)

    elif sensor_id == 2:
        rainfall = round(data['rainfall'] * 10)
        soil_moisture = round(data['soil_moisture'] * 10)
        flood_risk = data['flood_risk']
        rain_duration = data['rain_duration']

        packed = (rainfall & 0x1FFF) | ((soil_moisture & 0x3FF) << 13) | \
                ((flood_risk & 0x3) << 23) | ((rain_duration & 0x3F) << 25)
        return struct.pack('>I', packed)

    elif sensor_id == 3:
        co2 = data['co2'] - 300
        ozone = round(data['ozone'] * 10)
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
