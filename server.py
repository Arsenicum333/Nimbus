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

def send_json(sock, data, addr):
    sock.sendto(json.dumps(data).encode("utf-8"), addr)

def handle_packet(sock, data, addr):
    try:
        packet = json.loads(data.decode("utf-8"))
    except Exception:
        print(f"WARNING: Failed to decode packet from {addr}")
        return

    sensor_id = packet.get("sensor_id")
    token = packet.get("token")
    timestamp = packet.get("timestamp", int(time.time()))

    if packet.get("checksum") != compute_checksum(packet):
        print(f"INFO: {sensor_id} CORRUTPED DATA at {timestamp}. REQUESTING DATA")

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

    params = {
        key: value for key, value in packet.items()
        if key not in ("timestamp", "sensor_id", "token", "checksum", "low_battery")
    }

    low_battery = bool(packet.get("low_battery"))
    print(format_data(sensor_id, timestamp, params, low_battery))

    confirmation = {
        "timestamp": int(time.time()),
        "sensor_id": sensor_id,
        "type": PacketType.DATA_RECEIVED.value,
        "checksum": None
    }

    confirmation["checksum"] = compute_checksum(confirmation)
    send_json(sock, confirmation, addr)

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
        print("4) Exit")
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
            if server_thread and server_thread.is_alive():
                stop_event.set()
                server_thread.join()
            print("\nExiting...")
            break
        else:
            print("\nUnknown command")

if __name__ == "__main__":
    main()
