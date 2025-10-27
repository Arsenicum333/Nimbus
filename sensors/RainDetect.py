from enums.FloodRisk import FloodRisk

class RainDetect:
    def __init__(self, rainfall: float, soil_moisture: float, flood_risk: FloodRisk, rain_duration: int, low_battery: bool):
        self.rainfall = rainfall
        self.soil_moisture = soil_moisture
        self.flood_risk = flood_risk
        self.rain_duration = rain_duration
        self.low_battery = low_battery
