import random
import socket
import time
import threading

from enums.packetType import PacketType
from utils.binaryProtocol import *
from utils.formatData import format_data
from utils.userInput import choose_sensor

SERVER_IP = "0.0.0.0"
SERVER_PORT = 5005
BUFFER_SIZE = 1024

ACTIVITY_TIMEOUT = 15.0    # silence before the first activity check
CHECK_REPLY_TIMEOUT = 1.0  # unanswered check -> DISCONNECTED
CHECK_INTERVAL = 5.0       # spacing between activity checks
MAX_CHECKS = 10
NO_ACK_COUNT = 3

sensors = {}

sensors_lock = threading.Lock()
no_ack_mode = None
no_ack_counter = 0
no_ack_lock = threading.Lock()

lb_counter = 0
lb_lock = threading.Lock()

def update_sensor_activity(sensor_id, addr = None, token = None):
    with sensors_lock:
        if sensor_id in sensors:
            sensors[sensor_id]["last_seen"] = time.time()
            if token is not None:
                sensors[sensor_id]["token"] = token
            if addr is not None:
                sensors[sensor_id]["addr"] = addr
        elif addr is not None and token is not None:
            sensors[sensor_id] = {
                "token": token,
                "addr": addr,
                "last_seen": time.time(),
                "activity_checks_sent": 0,
                "last_activity_check_time": 0.0,
                "alerted": False,
                "disconnected": False
            }

def mark_alive(sensor_id):
    with sensors_lock:
        sensor_info = sensors.get(sensor_id)
        if sensor_info is None:
            return
        if sensor_info["disconnected"]:
            print(f"INFO: {sensor_id} RECONNECTED!")
        sensor_info["disconnected"] = False
        sensor_info["activity_checks_sent"] = 0

def send_activity_check(sock, sensor_id, addr):
    try:
        packet = pack_server_packet(PacketType.ACTIVITY_CHECK, sensor_id, int(time.time()))
        send_binary(sock, packet, addr)
        print(f"INFO: Activity check sent to {sensor_id}")
    except Exception as e:
        print(f"ERROR: Failed to send activity check to {sensor_id}: {e}")

def handle_packet(sock, data, addr):
    global no_ack_mode, no_ack_counter, lb_counter

    try:
        result = parse_binary_packet(data)
        if not result:
            packet_type = (data[0] >> 5) & 0x7 if data else None

            if packet_type == PacketType.DATA.value and len(data) >= 9:
                sensor_id = (data[0] >> 3) & 0x3
                timestamp = int.from_bytes(data[5:9], "big")
                print(f"INFO: {sensor_id} CORRUPTED DATA at {timestamp}. REQUESTING DATA")
                response = pack_server_packet(PacketType.REQUEST_RESEND, sensor_id, int(time.time()))
                send_binary(sock, response, addr)
            else:
                print(f"WARNING: Failed to decode packet from {addr}")
            return

        packet_type, packet_data = result

        if packet_type == 'REGISTRATION':
            sensor_id, timestamp, low_battery = packet_data
            print(f"INFO: {sensor_id} REGISTERED at {timestamp}")

            token = random.getrandbits(32)
            update_sensor_activity(sensor_id, addr, token)

            response = pack_registration_response(sensor_id, token, int(time.time()))
            send_binary(sock, response, addr)

        elif packet_type == 'DATA':
            sensor_id, token, timestamp, low_battery, sensor_data = packet_data

            with lb_lock:
                if low_battery and sensor_id == 1:
                    lb_counter += 1
                    print(f"Low Battery Counter: {lb_counter}")

            with sensors_lock:
                sensor_info = sensors.get(sensor_id)
                if not sensor_info or sensor_info["token"] != token:
                    print(f"WARNING: Invalid token from sensor {sensor_id}")
                    response = pack_server_packet(PacketType.INVALID_TOKEN, sensor_id, int(time.time()))
                    send_binary(sock, response, addr)
                    return

            update_sensor_activity(sensor_id)
            mark_alive(sensor_id)

            print(format_data(sensor_id, timestamp, sensor_data, low_battery))

            with no_ack_lock:
                if no_ack_mode == sensor_id:
                    no_ack_counter += 1
                    print(f"INFO: {sensor_id} no-ACK mode - counter: {no_ack_counter}/{NO_ACK_COUNT}")
                    if no_ack_counter >= NO_ACK_COUNT:
                        no_ack_mode = None
                        no_ack_counter = 0
                        print(f"INFO: {sensor_id} no-ACK mode disabled")
                    return

            response = pack_server_packet(PacketType.DATA_RECEIVED, sensor_id, int(time.time()))
            send_binary(sock, response, addr)

        elif packet_type == 'ACTIVITY_CONFIRMATION':
            sensor_id, token, timestamp, low_battery = packet_data

            update_sensor_activity(sensor_id)
            mark_alive(sensor_id)

    except Exception as e:
        print(f"ERROR: Handling packet from {addr}: {e}")

def monitor_sensors(stop_event, sock):
    while not stop_event.is_set():
        try:
            time.sleep(0.5)
            current_time = time.time()

            with sensors_lock:
                for sensor_id, sensor_info in sensors.items():
                    if current_time - sensor_info["last_seen"] <= ACTIVITY_TIMEOUT:
                        continue

                    checks_sent = sensor_info["activity_checks_sent"]
                    time_since_last_check = current_time - sensor_info["last_activity_check_time"]

                    # Check every CHECK_INTERVAL seconds, at most MAX_CHECKS times
                    if checks_sent == 0 or (checks_sent < MAX_CHECKS and time_since_last_check >= CHECK_INTERVAL):
                        send_activity_check(sock, sensor_id, sensor_info["addr"])
                        sensor_info["activity_checks_sent"] += 1
                        sensor_info["last_activity_check_time"] = current_time
                        sensor_info["alerted"] = False

                    # Check left unanswered for CHECK_REPLY_TIMEOUT -> DISCONNECTED
                    elif not sensor_info["alerted"] and time_since_last_check >= CHECK_REPLY_TIMEOUT:
                        print(f"WARNING: {sensor_id} DISCONNECTED!")
                        sensor_info["alerted"] = True
                        sensor_info["disconnected"] = True

        except Exception as e:
            print(f"ERROR: Monitoring sensors: {e}")

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
                handle_packet(sock, data, addr)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
    finally:
        sock.close()

def set_no_ack_device():
    global no_ack_mode, no_ack_counter

    sensor_id = choose_sensor("Select device for no-ACK mode:")

    with no_ack_lock:
        no_ack_mode = sensor_id
        no_ack_counter = 0

    print(f"INFO: Device {sensor_id} set to no-ACK mode (will ignore {NO_ACK_COUNT} ACKs)")

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
            print(f"\nConfiguration set to {SERVER_IP}:{SERVER_PORT}")
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
