class WindSense:
    def __init__(self, wind_speed: float, wind_gust: float, wind_direction: int, turbulence: float, low_battery: bool):
        self.wind_speed = wind_speed
        self.wind_gust = wind_gust
        self.wind_direction = wind_direction
        self.turbulence = turbulence
        self.low_battery = low_battery
