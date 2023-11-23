import RPi.GPIO as GPIO


class Fan:
    def set_power(self, power) -> None:
        pass

    def get_power(self) -> float:
        pass
    
    def destroy(self) -> None:
      pass


class DummyFan(Fan):
    def __init__(self, logger):
        self._logger = logger
        self._power = 0
        pass

    def set_power(self, power) -> None:
        self._power = power
        self._logger.info(f"Set power to {self._power}")
        pass

    def get_power(self):
        return self._power


class PwmFan(Fan):
    """A class the represent a PWM controlled fan"""

    def __init__(self, logger, pwm_pin, pwm_frequency):
        self._logger = logger
        self._frequency = pwm_frequency
        self._pin = pwm_pin

        GPIO.setup(self._pin, GPIO.OUT)
        self._fan = GPIO.PWM(self._pin, self._frequency)
        self._fan.start(0)

    def destroy(self):
        self._fan = None
        GPIO.cleanup(self._pin)

    def set_power(self, power):
        assert power >= 0
        assert power <= 1

        self._power = power
        self._fan.ChangeDutyCycle(int(self._power * 100))

    def get_power(self):
        return self._power
