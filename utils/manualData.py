from enums.sensorId import SensorID
from utils.userInput import get_float, get_int, get_yes_no

def manual_data(sensor):
    low_battery = get_yes_no("Low battery? (y/n): ")

    if sensor == SensorID.THERMONODE:
        from sensors.thermoNode import ThermoNode
        print("===== THERMONODE =====")
        temperature = get_float("Temperature (°C, -50 ... 60): ", -50, 60)
        humidity = get_float("Humidity (%, 0 ... 100): ", 0, 100)
        dew_point = get_float("Dew point (°C, -50 ... 60): ", -50, 60)
        pressure = get_float("Pressure (hPa, 800 ... 1100): ", 800, 1100, 2)
        return ThermoNode(temperature, humidity, dew_point, pressure, low_battery)

    elif sensor == SensorID.WINDSENSE:
        from sensors.windSense import WindSense
        print("===== WINDSENSE =====")
        wind_speed = get_float("Wind speed (m/s, 0 ... 50): ", 0, 50)
        wind_gust = get_float("Wind gust (m/s, 0 ... 70): ", 0, 70)
        wind_direction = get_int("Wind direction (°, 0 ... 359): ", 0, 359)
        turbulence = get_float("Turbulence (0.0 ... 1.0): ", 0.0, 1.0)
        return WindSense(wind_speed, wind_gust, wind_direction, turbulence, low_battery)

    elif sensor == SensorID.RAINDETECT:
        from sensors.rainDetect import RainDetect
        from enums.floodRisk import FloodRisk
        print("===== RAINDETECT =====")
        rainfall = get_float("Rainfall (mm, 0 ... 500): ", 0, 500)
        soil_moisture = get_float("Soil moisture (%, 0 ... 100): ", 0, 100)
        print("Flood risk options:", [f.name for f in FloodRisk])
        while True:
            flood_risk_input = input("Flood risk: ").upper()
            if flood_risk_input in FloodRisk.__members__:
                flood_risk = FloodRisk[flood_risk_input]
                break
            print("Invalid input.")
        rain_duration = get_int("Rain duration (minutes, 0 ... 60): ", 0, 60)
        return RainDetect(rainfall, soil_moisture, flood_risk, rain_duration, low_battery)

    elif sensor == SensorID.AIRQUALITYBOX:
        from sensors.airQualityBox import AirQualityBox
        print("===== AIRQUALITYBOX =====")
        co2 = get_int("CO2 (ppm, 300 ... 5000): ", 300, 5000)
        ozone = get_float("O3 (µg/m³, 0 ... 500): ", 0, 500)
        air_quality_index = get_int("Air Quality Index (0 ... 500): ", 0, 500)
        return AirQualityBox(co2, ozone, air_quality_index, low_battery)
