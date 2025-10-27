import socket
import json
import threading
import time

from enums.PacketType import PacketType
from enums.SensorID import SensorID
from data.ManualData import manual_data
from utils.SensorManager import SensorManager
from utils.Checksum import compute_checksum

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5005
BUFFER_SIZE = 65535

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(2.0)

tokens = {}
last_payloads = {}
corrupt_next = set()
state_lock = threading.Lock()

def send_json(data: dict, corrupt: bool = False, dest = None):
    data_copy = data.copy()

    if corrupt:
        data_copy["checksum"] = 1
    else:
        data_copy["checksum"] = compute_checksum(data_copy)

    destination = dest if dest is not None else (SERVER_IP, SERVER_PORT)
    sock.sendto(json.dumps(data_copy).encode("utf-8"), destination)

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

def build_payload(sensor_id, obj):
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

    return payload

def make_data(sensor_id, obj):
    payload = build_payload(sensor_id, obj)

    with state_lock:
        last_payloads[sensor_id] = payload.copy()
        do_corrupt = sensor_id in corrupt_next
        if do_corrupt:
            corrupt_next.discard(sensor_id)

    if do_corrupt:
        print(f"Sending corrupted packet for sensor {sensor_id}")
        send_json(payload, corrupt=True)
    else:
        send_json(payload, corrupt=False)

sensors = {
    SensorID.THERMONODE.value: SensorManager(SensorID.THERMONODE.value, make_data),
    SensorID.WINDSENSE.value: SensorManager(SensorID.WINDSENSE.value, make_data),
    SensorID.RAINDETECT.value: SensorManager(SensorID.RAINDETECT.value, make_data),
    SensorID.AIRQUALITYBOX.value: SensorManager(SensorID.AIRQUALITYBOX.value, make_data),
}

def listen():
    sock.settimeout(1.0)

    while True:
        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
            try:
                packet = json.loads(data.decode())
            except Exception:
                continue

            if packet.get("type") == PacketType.REQUEST_RESEND.value:
                sensorID = packet.get("sensor_id")

                with state_lock:
                    payload = last_payloads.get(sensorID)

                if payload:
                    send_json(payload, corrupt = False)
        except socket.timeout:
            continue
        except Exception:
            continue

def start_all_sensors():
    for sensor_id in sensors.keys():
        register(sensor_id)

    threading.Thread(target = listen, daemon = True).start()

    for sensor in sensors.values():
        sensor.start()

def stop_all_sensors():
    for sensor in sensors.values():
        sensor.stop()

def send_manual():
    for sensor in SensorID:
        print(f"{sensor.value}) {sensor.name}")

    try:
        sensorID_value = int(input("Select sensor ID (0–3): "))
        sensor = SensorID(sensorID_value)
    except (ValueError, KeyError):
        print("Invalid selection")
        return
    obj = manual_data(sensor)
    make_data(sensor.value, obj)
    print(f"Manual message for {sensor.name} sent")

def send_corrupted():
    for sensor in SensorID:
        print(f"{sensor.value}) {sensor.name}")

    try:
        sensorID_value = int(input("Select sensor to corrupt next automatic packet ID (0–3): "))
        if sensorID_value not in sensors:
            print("Invalid selection")
            return

        with state_lock:
            corrupt_next.add(sensorID_value)

        print(f"Next automatic packet of sensor {sensorID_value} will be corrupted")
    except Exception:
        print("Invalid input")

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
        print("4) Send corrupted next automatic packet")
        print("q) Quit")
        cmd = input().strip().lower()

        if cmd == "1":
            start_all_sensors()
        elif cmd == "2":
            stop_all_sensors()
        elif cmd == "3":
            send_manual()
        elif cmd == "4":
            send_corrupted()
        elif cmd == "q":
            stop_all_sensors()
            break
        else:
            print("Unknown command")

if __name__ == "__main__":
    main()
