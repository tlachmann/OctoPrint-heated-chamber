import RPi.GPIO as GPIO

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
    def __init__(self, logger, pin) -> None:
        super().__init__(logger)
        self._pin = pin

        GPIO.setup(self._pin, GPIO.OUT)
        GPIO.output(self._pin, GPIO.HIGH)

    def turn_on(self) -> None:
        GPIO.output(self._pin, GPIO.LOW)
        self._on = True
        self._logger.debug("Heater turned on")

    def turn_off(self) -> None:
        GPIO.output(self._pin, GPIO.HIGH)
        self._on = False
        self._logger.debug("Heater turned off")

    def state(self) -> bool:
        return self._on

    def destroy(self) -> None:
        GPIO.cleanup(self._pin)

