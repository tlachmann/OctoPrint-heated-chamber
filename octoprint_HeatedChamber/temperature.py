import random
import glob
import time
from octoprint.util import RepeatedTimer

class TemperatureSensor:
    def temperature(self) -> float:
        pass

class DummyTemperatureSensor(TemperatureSensor):
    def temperature(self) -> float:
        random.uniform(15.0, 70.0)


class Ds18b20(TemperatureSensor):
    def __init__(self, logger, update_frequency):
        self._logger = logger
        self._running=False
        self._update_frequency=update_frequency
        self._temperature=None
        self._device_file=None
        self._timer=RepeatedTimer(self._update_frequency, self._loop, condition=self.is_running, daemon=True)

    def is_running(self) -> bool:
        return self._running
    
    def temperature(self) -> float:
      return self._temperature

    def start(self) -> None:
        self._running=True
        self._timer.start()
        self._logger.info("Ds18b20 sensor started")

    def stop(self) -> None:
        self._timer.cancel()
        self._running=False
        self._logger.info("Ds18b20 sensor stopped")

    def _read_temp_raw(self):
        if self._device_file == None:
            base_dir = "/sys/bus/w1/devices/"
            device_folder = glob.glob(base_dir + "28*")[0]
            self._device_file = device_folder + "/w1_slave"

        f = open(self._device_file, "r")
        lines = f.readlines()
        f.close()
        return lines
    
    def _loop(self):
        self._logger.info("Ds18b20 looping...")

        lines = self._read_temp_raw()
        while lines[0].strip()[-3:] != "YES":
            time.sleep(0.2)
            lines = self._read_temp_raw()

        equals_pos = lines[1].find("t=")
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2 :]
            self._temperature = float(temp_string) / 1000.0
            self._logger.info(f"Ds18b20 looped with temperature={self._temperature}")

        self._logger.info("Ds18b20 looped.")
