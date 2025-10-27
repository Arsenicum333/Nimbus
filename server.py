import random
import socket
import json
import time
import threading

from utils.checksum import compute_checksum
from utils.formatData import format_data

SERVER_IP = "0.0.0.0"
SERVER_PORT = 5005
BUFFER_SIZE = 65535
sensors = {}  # sensor_id -> {"token": str, "addr": tuple}

def handle_packet(sock, data, addr):
    try:
        packet = json.loads(data.decode("utf-8"))
    except Exception:
        print(f"WARNING: Failed to decode packet from {addr}")
        return

    sensor_id = packet.get("sensor_id")
    token = packet.get("token")
    timestamp = packet.get("timestamp", int(time.time()))

    if not token:
        token = random.getrandbits(32)
        sensors[sensor_id] = {"token": token, "addr": addr}
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
        return

    if packet.get("checksum") != compute_checksum(packet):
        print(f"WARNING: Invalid checksum from sensor {sensor_id}")
        return

    params = {
        key: value for key, value in packet.items()
        if key not in ("timestamp", "sensor_id", "token", "checksum", "low_battery")
    }

    low_battery = bool(packet.get("low_battery"))
    print(format_data(sensor_id, timestamp, params, low_battery))

def listen(stop_event, server_ip, server_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((server_ip, server_port))
    sock.settimeout(1.0)

    try:
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                threading.Thread(target = handle_packet, args = (sock, data, addr), daemon = True).start()
            except socket.timeout:
                continue
    finally:
        sock.close()
        print("Server stopped")

if __name__ == "__main__":
    print("=== Server ===")
    SERVER_IP = input("Enter server IP [0.0.0.0]: ").strip() or SERVER_IP
    port_input = input("Enter server PORT [5005]: ").strip()
    SERVER_PORT = int(port_input) if port_input else SERVER_PORT
    print(f"\nServer listening on {SERVER_IP}:{SERVER_PORT}")

    stop_event = threading.Event()
    server_thread = threading.Thread(target = listen, args = (stop_event, SERVER_IP, SERVER_PORT), daemon = True)
    server_thread.start()

    print("\nMenu:")
    print("s) Stop server")

    while True:
        cmd = input().strip().lower()
        if cmd == "s":
            stop_event.set()
            server_thread.join()
            break
