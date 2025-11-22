import socket
import json
import threading
import time

from enums.PacketType import PacketType
from enums.SensorID import SensorID
from utils.ManualData import manual_data
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

pending_acks = {}  # sensor_id -> (payload, timestamp)
pending_lock = threading.Lock()

simulated_disconnected = set()
activity_check_counters = {}  # sensor_id -> count
activity_lock = threading.Lock()

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
    with activity_lock:
        if sensor_id in simulated_disconnected:
            return

    payload = build_payload(sensor_id, obj)

    with state_lock:
        last_payloads[sensor_id] = payload.copy()
        do_corrupt = sensor_id in corrupt_next

        if do_corrupt:
            corrupt_next.discard(sensor_id)

    if do_corrupt:
        send_json(payload, corrupt = True)
    else:
        send_json(payload, corrupt = False)

    with pending_lock:
        pending_acks[sensor_id] = (payload, time.time())

def check_pending_acks():
    while True:
        time.sleep(1)

        current_time = time.time()
        retry_sensors = []

        with state_lock:
            for sensor_id, (payload, timestamp) in list(pending_acks.items()):
                if current_time - timestamp >= 1.0:
                    retry_sensors.append((sensor_id, payload))
                    pending_acks[sensor_id] = (payload, current_time)

        for sensor_id, payload in retry_sensors:
            print(f"[{sensor_id}] No ACK received, retrying...")
            send_json(payload, corrupt = False)

def send_activity_confirmation(sensor_id):
    token = tokens.get(sensor_id)
    if not token:
        return

    response = {
        "timestamp": int(time.time()),
        "sensor_id": sensor_id,
        "type": PacketType.ACTIVITY_CONFIRMATION.value,
        "token": token
    }

    response["checksum"] = compute_checksum(response)
    send_json(response)
    print(f"[{sensor_id}] Sent activity confirmation")

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
            data, addr = sock.recvfrom(BUFFER_SIZE)
            try:
                packet = json.loads(data.decode())
            except Exception:
                continue

            if packet.get("type") == PacketType.REQUEST_RESEND.value:
                sensorID = packet.get("sensor_id")
                print(f"[{sensorID}] Resend request received")

                with state_lock:
                    payload = last_payloads.get(sensorID)

                if payload:
                    send_json(payload, corrupt = False)
                    print(f"[{sensorID}] Resent message")

            elif packet.get("type") == PacketType.DATA_RECEIVED.value:
                sensor_id = packet.get("sensor_id")

                with pending_lock:
                    if sensor_id in pending_acks:
                        del pending_acks[sensor_id]

            elif packet.get("type") == PacketType.ACTIVITY_CHECK.value:
                sensor_id = packet.get("sensor_id")

                with activity_lock:
                    if sensor_id in simulated_disconnected:
                        count = activity_check_counters.get(sensor_id, 0) + 1
                        activity_check_counters[sensor_id] = count
                        print(f"[{sensor_id}] Received activity check ({count}/3)")

                        if count >= 3:
                            send_activity_confirmation(sensor_id)
                            simulated_disconnected.discard(sensor_id)
                            activity_check_counters[sensor_id] = 0
                            print(f"[{sensor_id}] Reconnected and resumed normal operation")
                    else:
                        send_activity_confirmation(sensor_id)

        except socket.timeout:
            continue
        except Exception:
            continue

def start_all_sensors():
    for sensor_id in sensors.keys():
        register(sensor_id)

    threading.Thread(target = listen, daemon = True).start()
    threading.Thread(target = check_pending_acks, daemon = True).start()

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

    with activity_lock:
        if sensor.value in simulated_disconnected:
            return

    obj = manual_data(sensor)
    make_data(sensor.value, obj)
    print(f"Manual message for {sensor.name} sent")

def send_corrupted():
    for sensor in SensorID:
        print(f"{sensor.value}) {sensor.name}")

    try:
        sensorID_value = int(input("Select sensor ID to corrupt next automatic packet (0–3): "))
        if sensorID_value not in sensors:
            print("Invalid selection")
            return

        with state_lock:
            corrupt_next.add(sensorID_value)

        print(f"Next automatic packet of sensor {sensorID_value} will be corrupted")
    except Exception:
        print("Invalid input")

def simulate_disconnection():
    print("\nSelect device to simulate disconnection:")
    for sensor in SensorID:
        print(f"{sensor.value}) {sensor.name}")

    try:
        sensor_id = int(input("Enter sensor ID: "))
        if sensor_id not in [s.value for s in SensorID]:
            print("Invalid sensor ID")
            return

        with activity_lock:
            simulated_disconnected.add(sensor_id)
            activity_check_counters[sensor_id] = 0

        print(f"Device {sensor_id} is now simulated as disconnected - messages will not be sent")
    except ValueError:
        print("Invalid input")

def main():
    global SERVER_IP, SERVER_PORT

    print("===== Tester =====")

    while True:
        print("\nMenu:")
        print("1) Configure IP/PORT")
        print("2) Start automatic data sending")
        print("3) Stop automatic data sending")
        print("4) Send manual message")
        print("5) Send corrupted next automatic packet")
        print("6) Simulate device disconnection")
        print("7) Exit")
        cmd = input().strip().lower()

        if cmd == "1":
            SERVER_IP = input(f"\nEnter server IP [{SERVER_IP}]: ").strip() or SERVER_IP
            port_input = input(f"Enter server PORT [{SERVER_PORT}]: ").strip()
            SERVER_PORT = int(port_input) if port_input else SERVER_PORT
            print(f"Configuration set to {SERVER_IP}:{SERVER_PORT}")
        elif cmd == "2":
            start_all_sensors()
        elif cmd == "3":
            stop_all_sensors()
        elif cmd == "4":
            send_manual()
        elif cmd == "5":
            send_corrupted()
        elif cmd == "6":
            simulate_disconnection()
        elif cmd == "7":
            stop_all_sensors()
            print("\nExiting...")
            break
        else:
            print("\nUnknown command")

if __name__ == "__main__":
    main()
