import random
import socket
import json
import time
import threading

from enums.PacketType import PacketType
from utils.Checksum import compute_checksum
from utils.FormatData import format_data

SERVER_IP = "0.0.0.0"
SERVER_PORT = 5005
BUFFER_SIZE = 65535

sensors = {} # sensor_id -> {"token": str, "addr": tuple}

no_ack_mode = None
no_ack_counter = 0
no_ack_lock = threading.Lock()

activity_lock = threading.Lock()

def send_json(sock, data, addr):
    sock.sendto(json.dumps(data).encode("utf-8"), addr)

def update_sensor_activity(sensor_id, addr = None, reset_counters = False):
    with activity_lock:
        if sensor_id in sensors:
            sensors[sensor_id]["last_seen"] = time.time()

            if reset_counters:
                sensors[sensor_id]["activity_checks_sent"] = 0
                sensors[sensor_id]["disconnected_reported"] = 0
        elif addr is not None:
            token = random.getrandbits(32)
            sensors[sensor_id] = {
                "token": token,
                "addr": addr,
                "last_seen": time.time(),
                "activity_checks_sent": 0,
                "disconnected_reported": 0
            }

def send_activity_check(sock, sensor_id, addr):
    request = {
        "timestamp": int(time.time()),
        "sensor_id": sensor_id,
        "type": PacketType.ACTIVITY_CHECK.value
    }

    request["checksum"] = compute_checksum(request)
    send_json(sock, request, addr)
    print(f"[{sensor_id}] Sent activity check")

def handle_packet(sock, data, addr):
    global no_ack_mode, no_ack_counter

    try:
        packet = json.loads(data.decode("utf-8"))
    except Exception:
        print(f"WARNING: Failed to decode packet from {addr}")
        return

    sensor_id = packet.get("sensor_id")
    token = packet.get("token")
    timestamp = packet.get("timestamp", int(time.time()))

    update_sensor_activity(sensor_id, addr)

    is_activity_confirmation = (token is not None and
                               sensor_id is not None and
                               all(key in ("timestamp", "sensor_id", "token", "checksum", "type")
                                   for key in packet.keys()))

    if is_activity_confirmation:
        with activity_lock:
            if sensor_id in sensors and sensors[sensor_id]["activity_checks_sent"] >= 3:
                print(f"INFO: {sensor_id} RECONNECTED!")
                sensors[sensor_id]["activity_checks_sent"] = 0
                sensors[sensor_id]["disconnected_reported"] = 0
        return

    if packet.get("checksum") != compute_checksum(packet):
        print(f"INFO: {sensor_id} CORRUPTED DATA at {timestamp}. REQUESTING DATA")

        resend_request = {
            "timestamp": int(time.time()),
            "sensor_id": sensor_id,
            "type": PacketType.REQUEST_RESEND.value
        }

        resend_request["checksum"] = compute_checksum(resend_request)
        send_json(sock, resend_request, addr)
        return

    if not token:
        token = random.getrandbits(32)
        sensors[sensor_id] = {
            "token": token,
            "addr": addr,
            "last_seen": time.time(),
            "activity_checks_sent": 0,
            "disconnected_reported": 0
        }
        print(f"INFO: {sensor_id} REGISTERED at {timestamp}")

        response = {
            "timestamp": int(time.time()),
            "sensor_id": sensor_id,
            "token": token,
        }

        response["checksum"] = compute_checksum(response)
        sock.sendto(json.dumps(response).encode(), addr)
        return

    if sensor_id not in sensors or sensors[sensor_id]["token"] != token:
        print(f"WARNING: Invalid token from sensor {sensor_id}")

        invalid_token_response = {
            "timestamp": int(time.time()),
            "sensor_id": sensor_id,
            "type": PacketType.INVALID_TOKEN.value
        }
        invalid_token_response["checksum"] = compute_checksum(invalid_token_response)
        send_json(sock, invalid_token_response, addr)
        return

    update_sensor_activity(sensor_id, reset_counters = True)

    params = {
        key: value for key, value in packet.items()
        if key not in ("timestamp", "sensor_id", "token", "checksum", "low_battery", "type")
    }

    low_battery = bool(packet.get("low_battery"))
    print(format_data(sensor_id, timestamp, params, low_battery))

    with no_ack_lock:
        if no_ack_mode == sensor_id:
            no_ack_counter += 1
            print(f"[{sensor_id}] No ACK sent ({no_ack_counter}/3)")

            if no_ack_counter >= 3:
                no_ack_mode = None
                no_ack_counter = 0
            return

    confirmation = {
        "timestamp": int(time.time()),
        "sensor_id": sensor_id,
        "type": PacketType.DATA_RECEIVED.value,
        "checksum": None
    }

    confirmation["checksum"] = compute_checksum(confirmation)
    send_json(sock, confirmation, addr)

def monitor_sensors(stop_event, sock):
    while not stop_event.is_set():
        time.sleep(1)
        current_time = time.time()

        with activity_lock:
            sensors_to_check = list(sensors.items())

        for sensor_id, sensor_info in sensors_to_check:
            time_since_last_seen = current_time - sensor_info["last_seen"]

            if time_since_last_seen > 15:
                if sensor_info["activity_checks_sent"] == 0:
                    send_activity_check(sock, sensor_id, sensor_info["addr"])
                    sensor_info["activity_checks_sent"] = 1
                    sensor_info["last_activity_check_time"] = current_time
                    print(f"WARNING: {sensor_id} DISCONNECTED!")
                    sensor_info["disconnected_reported"] = 1

                elif sensor_info["activity_checks_sent"] < 10:
                    time_since_last_check = current_time - sensor_info["last_activity_check_time"]

                    if time_since_last_check > 5:
                        send_activity_check(sock, sensor_id, sensor_info["addr"])
                        sensor_info["activity_checks_sent"] += 1
                        sensor_info["last_activity_check_time"] = current_time

                        if sensor_info["activity_checks_sent"] == 2 and sensor_info["disconnected_reported"] < 2:
                            print(f"WARNING: {sensor_id} DISCONNECTED!")
                            sensor_info["disconnected_reported"] = 2

            else:
                if sensor_info["activity_checks_sent"] > 0:
                    sensor_info["activity_checks_sent"] = 0
                    sensor_info["disconnected_reported"] = 0

def listen(stop_event, server_ip, server_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((server_ip, server_port))
    sock.settimeout(1.0)

    monitor_thread = threading.Thread(target = monitor_sensors, args = (stop_event, sock), daemon = True)
    monitor_thread.start()

    try:
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                threading.Thread(target = handle_packet, args = (sock, data, addr), daemon = True).start()
            except socket.timeout:
                continue
    finally:
        sock.close()

def set_no_ack_device():
    global no_ack_mode, no_ack_counter

    print("\nSelect device for no-ACK mode:")
    from enums.SensorID import SensorID
    for sensor in SensorID:
        print(f"{sensor.value}) {sensor.name}")

    try:
        sensor_id = int(input("Enter sensor ID: "))
        if sensor_id not in [s.value for s in SensorID]:
            print("Invalid sensor ID")
            return

        with no_ack_lock:
            no_ack_mode = sensor_id
            no_ack_counter = 0
        print(f"Device {sensor_id} set to no-ACK mode (will ignore 3 ACKs)")
    except ValueError:
        print("Invalid input")

def main():
    global SERVER_IP, SERVER_PORT
    stop_event = threading.Event()
    server_thread = None

    print("===== Server =====")

    while True:
        print("\nMenu:")
        print("1) Configure IP/PORT")
        print("2) Start server")
        print("3) Stop server")
        print("4) Set device to no-ACK mode")
        print("5) Exit")
        cmd = input().strip().lower()

        if cmd == "1":
            SERVER_IP = input(f"\nEnter server IP [{SERVER_IP}]: ").strip() or SERVER_IP
            port_input = input(f"Enter server PORT [{SERVER_PORT}]: ").strip()
            SERVER_PORT = int(port_input) if port_input else SERVER_PORT
            print(f"Configuration set to {SERVER_IP}:{SERVER_PORT}")
        elif cmd == "2":
            if server_thread and server_thread.is_alive():
                print("\nServer is already running")
            else:
                stop_event.clear()
                server_thread = threading.Thread(target = listen, args = (stop_event, SERVER_IP, SERVER_PORT), daemon = True)
                server_thread.start()
                print(f"\nServer listening on {SERVER_IP}:{SERVER_PORT}")
        elif cmd == "3":
            if server_thread and server_thread.is_alive():
                stop_event.set()
                server_thread.join()
                print("\nServer stopped")
            else:
                print("\nServer is not running")
        elif cmd == "4":
            set_no_ack_device()
        elif cmd == "5":
            if server_thread and server_thread.is_alive():
                stop_event.set()
                server_thread.join()
            print("\nExiting...")
            break
        else:
            print("\nUnknown command")

if __name__ == "__main__":
    main()
