import random
import glob
import time
from os.path import basename
from octoprint.util import RepeatedTimer


class TemperatureSensor:
    def get_temperature(self) -> float:
        pass


class DummyTemperatureSensor(TemperatureSensor):
    def get_temperature(self) -> float:
        random.uniform(15.0, 70.0)


class Ds18b20(TemperatureSensor):
    def __init__(self, logger, update_frequency, device_id):
        self._logger = logger
        self._update_frequency = update_frequency
        self._device_id = device_id

        self._running = False
        self._temperature = None
        self._device_file = f"/sys/bus/w1/devices/{device_id}/w1_slave"
        self._timer = RepeatedTimer(
            self._update_frequency, self._loop, condition=self.is_running, daemon=True
        )

        self._logger.info(
            f"Ds18b20 initiated with update_frequency={self._update_frequency}, device_id={self._device_id}"
        )

    def is_running(self) -> bool:
        return self._running

    def get_temperature(self) -> float:
        return self._temperature

    def start(self) -> None:
        self._running = True
        self._timer.start()
        self._logger.debug("Ds18b20 sensor started")

    def stop(self) -> None:
        self._timer.cancel()
        self._running = False
        self._logger.debug("Ds18b20 sensor stopped")

    def _read_temp_raw(self):
        f = open(self._device_file, "r")
        lines = f.readlines()
        f.close()
        return lines

    def _loop(self):
        lines = self._read_temp_raw()
        while lines[0].strip()[-3:] != "YES":
            time.sleep(0.2)
            lines = self._read_temp_raw()

        equals_pos = lines[1].find("t=")
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2 :]
            self._temperature = float(temp_string) / 1000.0


def list_ds18b20_devices():
    base_dir = "/sys/bus/w1/devices/"
    folders = glob.glob(base_dir + "28*")
    device_names = list(map(lambda path: basename(path), folders))

    return device_names
