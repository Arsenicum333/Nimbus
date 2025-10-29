from enums.SensorID import SensorID

def manual_data(sensor):
    if sensor == SensorID.THERMONODE:
        from sensors.ThermoNode import ThermoNode
        print("===== THERMONODE =====")
        temperature = round(float(input("Temperature (°C, -50 … 60): ")), 1)
        humidity = round(float(input("Humidity (%, 0 … 100): ")), 1)
        dew_point = round(float(input("Dew point (°C, -50 … 60): ")), 1)
        pressure = round(float(input("Pressure (hPa, 800 … 1100): ")), 2)
        low_battery = input("Low battery? (y/n): ").lower() == "y"
        return ThermoNode(temperature, humidity, dew_point, pressure, low_battery)

    elif sensor == SensorID.WINDSENSE:
        from sensors.WindSense import WindSense
        print("===== WINDSENSE =====")
        wind_speed = round(float(input("Wind speed (m/s, 0 … 50): ")), 1)
        wind_gust = round(float(input("Wind gust (m/s, 0 … 70): ")), 1)
        wind_direction = int(input("Wind direction (°, 0 … 359): "))
        turbulence = round(float(input("Turbulence (0.0 … 1.0): ")), 1)
        low_battery = input("Low battery? (y/n): ").lower() == "y"
        return WindSense(wind_speed, wind_gust, wind_direction, turbulence, low_battery)

    elif sensor == SensorID.RAINDETECT:
        from sensors.RainDetect import RainDetect
        from enums.FloodRisk import FloodRisk
        print("===== RAINDETECT =====")
        rainfall = round(float(input("Rainfall (mm, 0 … 500): ")), 1)
        soil_moisture = round(float(input("Soil moisture (%, 0 … 100): ")), 1)
        print("Flood risk options:", [f.name for f in FloodRisk])
        flood_risk_input = input("Flood risk: ").upper()
        flood_risk = FloodRisk[flood_risk_input]
        rain_duration = int(input("Rain duration (minutes, 0 … 60): "))
        low_battery = input("Low battery? (y/n): ").lower() == "y"
        return RainDetect(rainfall, soil_moisture, flood_risk, rain_duration, low_battery)

    elif sensor == SensorID.AIRQUALITYBOX:
        from sensors.AirQualityBox import AirQualityBox
        print("===== AIRQUALITYBOX =====")
        co2 = int(input("CO₂ (ppm, 300 … 5000): "))
        ozone = round(float(input("O₃ (ppb, 0 … 500): ")), 1)
        air_quality_index = int(input("Air Quality Index (0 … 500): "))
        low_battery = input("Low battery? (y/n): ").lower() == "y"
        return AirQualityBox(co2, ozone, air_quality_index, low_battery)
