from enums.sensorId import SensorID

def get_float(prompt, min_val, max_val, decimals = 1):
    while True:
        try:
            value = round(float(input(prompt)), decimals)
            if not (min_val <= value <= max_val):
                print("Invalid input")
                continue
            return value
        except ValueError:
            print("Invalid input")

def get_int(prompt, min_val, max_val):
    while True:
        try:
            value = int(input(prompt))
            if not (min_val <= value <= max_val):
                print("Invalid input")
                continue
            return value
        except ValueError:
            print("Invalid input.")

def get_yes_no(prompt):
    while True:
        value = input(prompt).lower()
        if value in ("y", "n"):
            return value == "y"
        print("Invalid input")

def choose_sensor(title):
    print(f"\n{title}")
    for sensor in SensorID:
        print(f"{sensor.value}) {sensor.name}")
    return get_int("Enter sensor ID: ", 0, len(SensorID) - 1)
