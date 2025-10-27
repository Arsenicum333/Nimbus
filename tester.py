import socket
import json
import time
import threading

from enums.SensorID import SensorID
from data.manualData import manual_data
from data.randomData import random_data
from utils.checksum import compute_checksum

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5005
BUFFER_SIZE = 65535

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(2.0)
tokens = {}

auto_thread = None
auto_running = False

def send_json(data: dict):
    data["checksum"] = compute_checksum(data)
    sock.sendto(json.dumps(data).encode("utf-8"), (SERVER_IP, SERVER_PORT))

def register(sensor_id):
    packet = {
        "timestamp": int(time.time()),
        "sensor_id": sensor_id,
    }

    send_json(packet)

    try:
        data, _ = sock.recvfrom(BUFFER_SIZE)
        response = json.loads(data.decode())

        if "token" in response:
            tokens[sensor_id] = response["token"]
            print(f"{sensor_id} registered (token={response['token']})")
    except Exception:
        print(f"{sensor_id} registration timeout")

def make_data(sensor_id, obj):
    token = tokens.get(sensor_id)

    if not token:
        register(sensor_id)
        token = tokens.get(sensor_id)

    payload = {
        "timestamp": int(time.time()),
        "sensor_id": sensor_id,
        "token": token,
        "low_battery": int(getattr(obj, "low_battery", False)),
    }

    for key, value in vars(obj).items():
        if key != "low_battery":
            payload[key] = value.value if hasattr(value, "value") else value

    send_json(payload)

def send_manual():
    for sensor in SensorID:
        print(f"{sensor.value}) {sensor.name}")

    try:
        sensorID_val = int(input("Select sensor ID (0–3): "))
        sensor = SensorID(sensorID_val)
    except (ValueError, KeyError):
        print("Invalid selection")
        return

    obj = manual_data(sensor)
    make_data(sensor.value, obj)
    print(f"Manual message for {sensor.name} sent")

def auto_loop():
    global auto_running

    sensors = {
        SensorID.THERMONODE: random_data,
        SensorID.WINDSENSE: random_data,
        SensorID.RAINDETECT: random_data,
        SensorID.AIRQUALITYBOX: random_data,
    }

    for sensorID in sensors:
        register(sensorID.value)

    print("Automatic sending started (every 10 seconds)")

    while auto_running:
        for sensorID, function in sensors.items():
            make_data(sensorID.value, function(sensorID.value))

        for _ in range(10):
            if not auto_running:
                break
            time.sleep(1)

    print("Automatic sending stopped")

def start_auto():
    global auto_thread, auto_running

    if auto_running:
        print("Already running")
        return

    auto_running = True
    auto_thread = threading.Thread(target = auto_loop, daemon = True)
    auto_thread.start()

def stop_auto():
    global auto_running
    auto_running = False

def main():
    print("=== FIITMeteo ===")
    global SERVER_IP, SERVER_PORT
    SERVER_IP = input(f"Enter server IP [{SERVER_IP}]: ").strip() or SERVER_IP
    port_in = input(f"Enter server PORT [{SERVER_PORT}]: ").strip()
    SERVER_PORT = int(port_in) if port_in else SERVER_PORT

    while True:
        print("\nMenu:")
        print("1) Start automatic data sending")
        print("2) Stop automatic data sending")
        print("3) Send manual message")
        print("q) Quit")
        cmd = input().strip().lower()

        if cmd == "1":
            start_auto()
        elif cmd == "2":
            stop_auto()
        elif cmd == "3":
            send_manual()
        elif cmd == "q":
            stop_auto()
            break
        else:
            print("Unknown command")

if __name__ == "__main__":
    main()
