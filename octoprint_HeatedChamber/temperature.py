import random
import glob
import time


class TemperatureSensor:
    def read_temp(self) -> float:
        pass


class DummyTemperatureSensor(TemperatureSensor):
    def read_temp(self) -> float:
        random.uniform(15.0, 70.0)


class Ds18b20(TemperatureSensor):
    def __init__(self):
        base_dir = "/sys/bus/w1/devices/"
        device_folder = glob.glob(base_dir + "28*")[0]
        self.device_file = device_folder + "/w1_slave"

    def __read_temp_raw(self):
        f = open(self.device_file, "r")
        lines = f.readlines()
        f.close()
        return lines

    def read_temp(self):
        lines = self.__read_temp_raw()
        while lines[0].strip()[-3:] != "YES":
            time.sleep(0.2)
            lines = self.__read_temp_raw()
        equals_pos = lines[1].find("t=")
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2 :]
            temp_c = float(temp_string) / 1000.0
            return temp_c
