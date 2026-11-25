import socket
import threading
import time

from enums.sensorId import SensorID
from utils.manualData import manual_data
from utils.userInput import choose_sensor
from utils.sensorManager import SensorManager
from utils.binaryProtocol import *

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5005
BUFFER_SIZE = 1024
REGISTRATION_TIMEOUT = 2.0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 0))
sock.settimeout(1.0)

tokens = {}
registered_events = {sensor.value: threading.Event() for sensor in SensorID}
last_payloads = {}
corrupt_next = set()
simulated_disconnected = set()
activity_check_counters = {}

tokens_lock = threading.Lock()
payloads_lock = threading.Lock()
corrupt_lock = threading.Lock()
disconnect_lock = threading.Lock()

pending_acks = {}
pending_acks_lock = threading.Lock()

server_address = (SERVER_IP, SERVER_PORT)

def register(sensor_id):
    # The response is received by handle_server_messages(), which sets the event
    event = registered_events[sensor_id]
    event.clear()

    try:
        packet = pack_registration(sensor_id, int(time.time()), False)
        send_binary(sock, packet, server_address)
    except Exception as e:
        print(f"ERROR: [{sensor_id}] Registration failed: {e}")
        return False

    if not event.wait(REGISTRATION_TIMEOUT):
        print(f"ERROR: [{sensor_id}] Registration timeout")
        return False
    return True

def build_payload(sensor_id, obj):
    with tokens_lock:
        token = tokens.get(sensor_id)

    if token is None:
        if not register(sensor_id):
            return None
        with tokens_lock:
            token = tokens.get(sensor_id)
        if token is None:
            return None

    low_battery = getattr(obj, "low_battery", False)

    sensor_data = {}
    for key, value in vars(obj).items():
        if key != "low_battery":
            sensor_data[key] = value.value if hasattr(value, "value") else value

    return sensor_id, token, int(time.time()), low_battery, sensor_data

def make_data(sensor_id, obj):
    try:
        with disconnect_lock:
            if sensor_id in simulated_disconnected:
                return

        payload = build_payload(sensor_id, obj)
        if payload is None:
            print(f"ERROR: [{sensor_id}] Failed to build payload")
            return

        sensor_id, token, timestamp, low_battery, sensor_data = payload

        with payloads_lock:
            last_payloads[sensor_id] = payload

        with corrupt_lock:
            should_corrupt = sensor_id in corrupt_next
            if should_corrupt:
                corrupt_next.discard(sensor_id)
                print(f"INFO: [{sensor_id}] Corruption flag set - will corrupt this packet")

        packet = pack_data(sensor_id, token, timestamp, low_battery, sensor_data)

        if should_corrupt:
            corrupted_packet = packet[:-4] + b'\x00\x00\x00\x01'
            send_binary(sock, corrupted_packet, server_address)
            print(f"INFO: [{sensor_id}] Sent CORRUPTED data (checksum set to 1)")

        else:
            send_binary(sock, packet, server_address)
            print(f"INFO: [{sensor_id}] Sent data")

            with pending_acks_lock:
                pending_acks[sensor_id] = {
                    'packet': packet,
                    'last_sent_time': time.time(),
                    'retry_count': 0,
                    'original_timestamp': timestamp
                }

    except Exception as e:
        print(f"ERROR: [{sensor_id}] Failed to send data: {e}")

def check_pending_acks():
    while True:
        time.sleep(1)
        current_time = time.time()
        retry_list = []

        with pending_acks_lock:
            for sensor_id, ack_info in list(pending_acks.items()):
                if current_time - ack_info['last_sent_time'] >= 1.0 and ack_info['retry_count'] < 10:
                    retry_list.append((sensor_id, ack_info))

        for sensor_id, ack_info in retry_list:
            send_binary(sock, ack_info['packet'], server_address)
            print(f"INFO: [{sensor_id}] Retry sending data (no ACK received, attempt {ack_info['retry_count'] + 1})")

            with pending_acks_lock:
                if sensor_id in pending_acks:
                    pending_acks[sensor_id]['last_sent_time'] = current_time
                    pending_acks[sensor_id]['retry_count'] += 1

        with pending_acks_lock:
            for sensor_id, ack_info in list(pending_acks.items()):
                if ack_info['retry_count'] >= 10:
                    del pending_acks[sensor_id]
                    print(f"WARNING: [{sensor_id}] Max retry attempts reached")

def handle_server_messages():
    while True:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            result = parse_binary_packet(data)

            if not result:
                continue

            packet_type, packet_data = result

            if packet_type == 'REGISTRATION_RESPONSE':
                sensor_id, token, timestamp = packet_data
                with tokens_lock:
                    tokens[sensor_id] = token
                print(f"INFO: [{sensor_id}] Registered successfully (token={token})")
                registered_events[sensor_id].set()

            elif packet_type == 'REQUEST_RESEND':
                sensor_id, timestamp = packet_data
                print(f"INFO: [{sensor_id}] Received resend request")

                with payloads_lock:
                    payload = last_payloads.get(sensor_id)

                if payload:
                    sensor_id, token, timestamp, low_battery, sensor_data = payload

                    packet = pack_data(sensor_id, token, timestamp, low_battery, sensor_data)
                    send_binary(sock, packet, server_address)
                    print(f"INFO: [{sensor_id}] Data resent")

            elif packet_type == 'DATA_RECEIVED':
                sensor_id, timestamp = packet_data
                with pending_acks_lock:
                    if sensor_id in pending_acks:
                        del pending_acks[sensor_id]
                print(f"INFO: [{sensor_id}] Data acknowledged by server")

            elif packet_type == 'ACTIVITY_CHECK':
                sensor_id, timestamp = packet_data
                print(f"INFO: [{sensor_id}] Received activity check")

                with disconnect_lock:
                    if sensor_id in simulated_disconnected:
                        activity_count = activity_check_counters.get(sensor_id, 0) + 1
                        activity_check_counters[sensor_id] = activity_count

                        if activity_count >= 3:
                            with tokens_lock:
                                token = tokens.get(sensor_id)
                            if token is not None:
                                packet = pack_activity_confirmation(sensor_id, token, int(time.time()), False)
                                send_binary(sock, packet, server_address)
                                simulated_disconnected.discard(sensor_id)
                                activity_check_counters[sensor_id] = 0
                                print(f"INFO: [{sensor_id}] Reconnected after 3 activity checks")
                        else:
                            print(f"INFO: [{sensor_id}] Ignoring activity check ({activity_count}/3)")
                    else:
                        with tokens_lock:
                            token = tokens.get(sensor_id)
                        if token is not None:
                            packet = pack_activity_confirmation(sensor_id, token, int(time.time()), False)
                            send_binary(sock, packet, server_address)
                            print(f"INFO: [{sensor_id}] Sent activity confirmation")

            elif packet_type == 'INVALID_TOKEN':
                sensor_id, timestamp = packet_data
                print(f"WARNING: [{sensor_id}] Invalid token - re-registering")
                with tokens_lock:
                    if sensor_id in tokens:
                        del tokens[sensor_id]
                # register() waits for a response that only this thread can receive
                threading.Thread(target = register, args = (sensor_id,), daemon = True).start()

        except socket.timeout:
            continue
        except ConnectionResetError:
            continue
        except Exception as e:
            print(f"ERROR: Handling server message: {e}")

def start_all_sensors():
    try:
        for sensor_id in sensors.keys():
            register(sensor_id)

        for sensor in sensors.values():
            sensor.start()

    except Exception as e:
        print(f"ERROR: Starting sensors: {e}")

def stop_all_sensors():
    for sensor in sensors.values():
        sensor.stop()

    with pending_acks_lock:
        pending_acks.clear()

    print("INFO: All sensors stopped")

def send_manual_message():
    sensor_id = choose_sensor("Select sensor for manual message:")
    sensor_obj = manual_data(SensorID(sensor_id))

    make_data(sensor_id, sensor_obj)
    print(f"INFO: Manual message sent for sensor {sensor_id}")

def corrupt_next_packet():
    sensor_id = choose_sensor("Select sensor to corrupt next packet:")

    with corrupt_lock:
        corrupt_next.add(sensor_id)

    print(f"INFO: Next packet from sensor {sensor_id} will be corrupted")

def simulate_disconnection():
    sensor_id = choose_sensor("Select sensor to simulate disconnection:")

    with disconnect_lock:
        simulated_disconnected.add(sensor_id)
        activity_check_counters[sensor_id] = 0

    print(f"INFO: Sensor {sensor_id} simulated as disconnected")

sensors = {
    SensorID.THERMONODE.value: SensorManager(SensorID.THERMONODE.value, make_data),
    SensorID.WINDSENSE.value: SensorManager(SensorID.WINDSENSE.value, make_data),
    SensorID.RAINDETECT.value: SensorManager(SensorID.RAINDETECT.value, make_data),
    SensorID.AIRQUALITYBOX.value: SensorManager(SensorID.AIRQUALITYBOX.value, make_data),
}

def main():
    global SERVER_IP, SERVER_PORT, server_address

    print("===== Tester =====")

    # Background workers run for the whole lifetime of the program
    threading.Thread(target = handle_server_messages, daemon = True).start()
    threading.Thread(target = check_pending_acks, daemon = True).start()

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
            server_address = (SERVER_IP, SERVER_PORT)
            print(f"\nConfiguration set to {SERVER_IP}:{SERVER_PORT}")
        elif cmd == "2":
            start_all_sensors()
        elif cmd == "3":
            stop_all_sensors()
        elif cmd == "4":
            send_manual_message()
        elif cmd == "5":
            corrupt_next_packet()
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
