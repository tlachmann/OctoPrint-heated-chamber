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
    def __init__(self, logger, pin, relay_mode) -> None:
        super().__init__(logger)
        self._pin = pin
        self._relay_mode = relay_mode

        if relay_mode == RelayMode.ACTIVE_HIGH:
            self._on_value = 1
            self._off_value = 0
        else:
            self._on_value = 0
            self._off_value = 1

        self._pi = pigpio.pi()

        self._pi.set_mode(self._pin, pigpio.OUTPUT)
        self._pi.set_pull_up_down(self._pin, pigpio.PUD_UP)

    def turn_on(self) -> None:
        self._pi.write(self._pin, self._on_value)
        self._on = True
        self._logger.debug("Heater turned on")

    def turn_off(self) -> None:
        self._pi.write(self._pin, self._off_value)
        self._on = False
        self._logger.debug("Heater turned off")

    def state(self) -> bool:
        return self._on

    def destroy(self) -> None:
        self._pi.stop()
