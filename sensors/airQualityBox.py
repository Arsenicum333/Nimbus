class AirQualityBox:
    def __init__(self, co2: int, ozone: float, air_quality_index: int, low_battery: bool):
        self.co2 = co2
        self.ozone = ozone
        self.air_quality_index = air_quality_index
        self.low_battery = low_battery
