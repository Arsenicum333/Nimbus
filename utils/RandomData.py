import random

from enums.FloodRisk import FloodRisk
from sensors.AirQualityBox import AirQualityBox
from sensors.RainDetect import RainDetect
from sensors.ThermoNode import ThermoNode
from sensors.WindSense import WindSense

def random_data(sensorID):
    if sensorID == 0:
        return ThermoNode(
        temperature = round(random.uniform(-50, 60), 1),
        humidity = round(random.uniform(0, 100), 1),
        dew_point = round(random.uniform(-50, 60), 1),
        pressure = round(random.uniform(800, 1100), 2),
        low_battery = False,
    )
    elif sensorID == 1:
        return WindSense(
        wind_speed = round(random.uniform(0, 50), 1),
        wind_gust = round(random.uniform(0, 70), 1),
        wind_direction = random.randint(0, 359),
        turbulence = round(random.uniform(0, 1), 1),
        low_battery = False,
    )
    elif sensorID == 2:
        return RainDetect(
        rainfall = round(random.uniform(0, 500), 1),
        soil_moisture = round(random.uniform(0, 100), 1),
        flood_risk = random.choice(list(FloodRisk)),
        rain_duration = random.randint(0, 60),
        low_battery = False,
    )
    elif sensorID == 3:
        return AirQualityBox(
        co2 = random.randint(300, 5000),
        ozone = round(random.uniform(0, 500), 1),
        air_quality_index = random.randint(0, 500),
        low_battery = False,
    )
