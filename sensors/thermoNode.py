class ThermoNode:
    def __init__(self, temperature: float, humidity: float, dew_point: float, pressure: float, low_battery: bool):
        self.temperature = temperature
        self.humidity = humidity
        self.dew_point = dew_point
        self.pressure = pressure
        self.low_battery = low_battery
