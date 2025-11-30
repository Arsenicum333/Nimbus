import random
import socket
import time
import threading

from enums.PacketType import PacketType
from utils.BinaryProtocol import *
from utils.FormatData import format_data

SERVER_IP = "0.0.0.0"
SERVER_PORT = 5005
BUFFER_SIZE = 1024

sensors = {} # sensor_id -> {"token": str, "addr": tuple}

sensors_lock = threading.Lock()
no_ack_mode = None
no_ack_counter = 0
no_ack_lock = threading.Lock()

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
                "disconnected": False
            }

def send_activity_check(sock, sensor_id, addr):
    try:
        packet = pack_server_packet(PacketType.ACTIVITY_CHECK, sensor_id, int(time.time()))
        send_binary(sock, packet, addr)
        print(f"INFO: Activity check sent to {sensor_id}")
    except Exception as e:
        print(f"ERROR: Failed to send activity check to {sensor_id}: {e}")

def handle_packet(sock, data, addr):
    global no_ack_mode, no_ack_counter

    try:
        result = parse_binary_packet(data)
        if not result:
            print(f"WARNING: Failed to decode packet from {addr}")

            if len(data) > 0:
                try:
                    first_byte = data[0]
                    packet_type = (first_byte >> 5) & 0x7
                    sensor_id = (first_byte >> 3) & 0x3

                    if packet_type == PacketType.DATA.value:
                        print(f"INFO: {sensor_id} CORRUPTED DATA. REQUESTING RESEND")
                        response = pack_server_packet(PacketType.REQUEST_RESEND, sensor_id, int(time.time()))
                        send_binary(sock, response, addr)
                except:
                    print(f"WARNING: Could not extract sensor_id from corrupted packet")
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

            with sensors_lock:
                sensor_info = sensors.get(sensor_id)
                if not sensor_info or sensor_info["token"] != token:
                    print(f"WARNING: Invalid token from sensor {sensor_id}")
                    response = pack_server_packet(PacketType.INVALID_TOKEN, sensor_id, int(time.time()))
                    send_binary(sock, response, addr)
                    return

            update_sensor_activity(sensor_id)

            with sensors_lock:
                if sensors[sensor_id].get("disconnected", False):
                    print(f"INFO: {sensor_id} RECONNECTED!")
                    sensors[sensor_id]["disconnected"] = False
                    sensors[sensor_id]["activity_checks_sent"] = 0

            print(format_data(sensor_id, timestamp, sensor_data, low_battery))

            with no_ack_lock:
                if no_ack_mode == sensor_id:
                    no_ack_counter += 1
                    print(f"INFO: {sensor_id} no-ACK mode - counter: {no_ack_counter}/3")
                    if no_ack_counter >= 3:
                        no_ack_mode = None
                        no_ack_counter = 0
                        print(f"INFO: {sensor_id} no-ACK mode disabled")
                    return

            response = pack_server_packet(PacketType.DATA_RECEIVED, sensor_id, int(time.time()))
            send_binary(sock, response, addr)

        elif packet_type == 'ACTIVITY_CONFIRMATION':
            sensor_id, token, timestamp, low_battery = packet_data

            update_sensor_activity(sensor_id)

            with sensors_lock:
                if sensors[sensor_id].get("disconnected", False):
                    print(f"INFO: {sensor_id} RECONNECTED!")
                    sensors[sensor_id]["disconnected"] = False
                    sensors[sensor_id]["activity_checks_sent"] = 0

        elif packet_type in ['DATA_RECEIVED', 'REQUEST_RESEND', 'INVALID_TOKEN', 'ACTIVITY_CHECK']:
            print(f"WARNING: Received server packet {packet_type} from client")

    except Exception as e:
        print(f"ERROR: Handling packet from {addr}: {e}")

def monitor_sensors(stop_event, sock):
    while not stop_event.is_set():
        try:
            time.sleep(0.5)
            current_time = time.time()

            with sensors_lock:
                sensors_to_check = list(sensors.items())

            for sensor_id, sensor_info in sensors_to_check:
                time_since_last_seen = current_time - sensor_info["last_seen"]

                if time_since_last_seen > 15:
                    if sensor_info["activity_checks_sent"] == 0:
                        send_activity_check(sock, sensor_id, sensor_info["addr"])
                        sensor_info["activity_checks_sent"] = 1
                        sensor_info["last_activity_check_time"] = current_time
                        print(f"WARNING: {sensor_id} DISCONNECTED!")
                        sensor_info["disconnected"] = True

                    elif sensor_info["activity_checks_sent"] < 10:
                        time_since_last_check = current_time - sensor_info["last_activity_check_time"]

                        if sensor_info["activity_checks_sent"] == 1 and time_since_last_check >= 5.0:
                            send_activity_check(sock, sensor_id, sensor_info["addr"])
                            sensor_info["activity_checks_sent"] = 2
                            sensor_info["last_activity_check_time"] = current_time
                            print(f"WARNING: {sensor_id} DISCONNECTED!")

                        elif sensor_info["activity_checks_sent"] >= 2 and time_since_last_check >= 5.0:
                            send_activity_check(sock, sensor_id, sensor_info["addr"])
                            sensor_info["activity_checks_sent"] += 1
                            sensor_info["last_activity_check_time"] = current_time

                else:
                    if sensor_info["activity_checks_sent"] > 0:
                        was_disconnected = sensor_info.get("disconnected", False)
                        sensor_info["activity_checks_sent"] = 0
                        if was_disconnected:
                            print(f"INFO: {sensor_id} RECONNECTED!")
                        sensor_info["disconnected"] = False

        except Exception as e:
            print(f"ERROR: Monitoring sensors: {e}")

def listen(stop_event, server_ip, server_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((server_ip, server_port))
    sock.settimeout(1.0)

    monitor_thread = threading.Thread(target=monitor_sensors, args=(stop_event, sock), daemon=True)
    monitor_thread.start()

    print(f"INFO: Server listening on {server_ip}:{server_port}")

    try:
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                threading.Thread(target=handle_packet, args=(sock, data, addr), daemon=True).start()
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
            print("ERROR: Invalid sensor ID")
            return

        with no_ack_lock:
            no_ack_mode = sensor_id
            no_ack_counter = 0

        print(f"INFO: Device {sensor_id} set to no-ACK mode (will ignore 3 ACKs)")
    except ValueError:
        print("ERROR: Invalid input")

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
