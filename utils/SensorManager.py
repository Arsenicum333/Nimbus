import threading
import time

from utils.RandomData import random_data

class SensorManager:
    def __init__(self, sensor_id, send_function):
        self.sensor_id = sensor_id
        self.send_function = send_function  # make_data(sensor_id, obj)
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            print(f"[{self.sensor_id}] already running")
            return

        self.running = True
        self.thread = threading.Thread(target = self._loop, daemon = True)
        self.thread.start()
        print(f"[{self.sensor_id}] started")

    def stop(self):
        self.running = False
        print(f"[{self.sensor_id}] stopped")

    def _loop(self):
        while self.running:
            self.send_function(self.sensor_id, random_data(self.sensor_id))

            for _ in range(10):
                if not self.running:
                    break
                time.sleep(1)
