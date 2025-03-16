import pigpio

from enum import Enum


class RelayMode(Enum):
    ACTIVE_LOW = 0
    ACTIVE_HIGH = 1


class Heater:
    def __init__(self, logger) -> None:
        self._logger = logger

    def destroy(self) -> None:
        pass

    def turn_on(self) -> None:
        pass

    def turn_off(self) -> None:
        pass

    def state(self) -> bool:
        pass

    def toggle(self) -> None:
        if self.state():
            self.turn_off()
        else:
            self.turn_on()


class RelayHeater(Heater):
    def __init__(self, logger, pin, relay_mode, heaterPWMMode) -> None:
        super().__init__(logger)
        try:
            self._logger = logger
            self._pin = pin
            self._relay_mode = relay_mode
            self._heaterPWMMode = heaterPWMMode

            if relay_mode == RelayMode.ACTIVE_HIGH:
                self._on_value = 1
                self._off_value = 0
            else:
                self._on_value = 0
                self._off_value = 1

            self._pi = pigpio.pi()
            if not self._pi.connected:
                self._logger.error("Error connectiong to pigpio")

            self._pi.set_mode(self._pin, pigpio.OUTPUT)
            #self._pi.set_pull_up_down(self._pin, pigpio.PUD_UP)
            
            if self._heaterPWMMode:
                self._pi.set_PWM_frequency(self._pin,  200)
            self._pi.set_PWM_range(self._pin, 100)
        except Exception as ex:
            self._logger.warn(f"Heater Init Exception: {ex}")

    def turn_on(self) -> None:
        try:
            self._pi.write(self._pin, self._on_value)
            self._on = True
            self._logger.debug("Heater turned on")
        except Exception as ex:
            self._logger.warn(f"Heater TurnOn Exception: {ex}")
     

    def turn_off(self) -> None:
        try:
            self._pi.write(self._pin, self._off_value)
            self._on = False
            self._logger.debug("Heater turned off")
        except Exception as ex:
            self._logger.warn(f"Heater TurnOff Exception: {ex}")

    def state(self) -> bool:
        return self._on

    def destroy(self) -> None:
        self._pi.stop()

    def set_power(self, power):
        try:
            #assert power >= 0
            #assert power <= 100

            self._power = power
            self._logger.debug(f"Set power to {self._power}")
            self._pi.set_PWM_dutycycle(
                self._pin, self._power
            )
        except Exception as ex:
            self._logger.warn(f"Heater SetPower Exception: {ex}")


    def get_power(self):
        return self._power