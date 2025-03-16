import random
import glob
import time
from os.path import basename
from octoprint.util import RepeatedTimer
import threading


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
        
        self._tempSens_event_object = threading.Event()

        self._running = False
        self._temperature = None
        self._device_file = f"/mnt/1wire/{device_id}/temperature"
        self._timer = RepeatedTimer(
            self._update_frequency, self._loop, condition=self.is_running, daemon=True
        )

        self._logger.info(
            f"Ds18b20 initiated with update_frequency={self._update_frequency}, device_id={self._device_id}"
        )

    def is_running(self) -> bool:
        return self._timer.is_alive()

    def get_temperature(self):
        try:
            self._event_set = self._tempSens_event_object.wait(5)
            if self._event_set: # and self._temperature is float:
                return self._temperature
            else:                    
                return None
            #temp_transmit = None
            #self._logger.debug("get_temperature() 1 temp_transmit %s", temp_transmit)
            #temp_transmit = self._temperature
            #self._logger.debug("get_temperature() 2 temp_transmit %s", temp_transmit)
            #self._logger.debug("get_temperature() 3 self._temperature %s", self._temperature)

            #self._temperature = None
            #self._logger.debug("get_temperature() 4 temp_transmit %s", temp_transmit)
            #self._logger.debug("get_temperature() 5 self._temperature %s", self._temperature)
            #return temp_transmit
        except Exception as e:
            self._logger.warn("get_temperature() X Ds18b20 sensor get_temp %s", e)
            return -1

    def start(self) -> None:
        self._running = True
        self._timer.start()
        self._logger.debug("Tempsensor start() Ds18b20 sensor started")

    def stop(self) -> None:
        self._timer.cancel()
        self._running = False
        self._logger.debug("Tempsesnor Stop() Ds18b20 sensor stopped")

    def _read_temp_raw(self):
        lines = ""
        f = open(self._device_file, "r")
        lines = f.readline()
        f.close()
        return lines

    def _loop(self):
        self._tempSens_event_object.clear()
        self._temperature = None
        try:
            if self._running and self._read_temp_raw() is not None:
                self._temperature = float(self._read_temp_raw())
                self._tempSens_event_object.set()
                #self._logger.debug("Tempsensor Loop 1: Raw temperature: %s", self._temperature)
            else: 
                #self._logger.debug("Tempsensor Loop 2: Tempsensor stopped running: %s", self._temperature)
                self._temperature=None
        except Exception as e:
            self._logger.warn("Tempsensor Loop X: Ds18b20 sensor loop Exception %s", e)

            

        


def list_ds18b20_devices():
    base_dir = "/mnt/1wire/"
    folders = glob.glob(base_dir + "28*")
    device_names = list(map(lambda path: basename(path), folders))

    return device_names
