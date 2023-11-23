import pigpio

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
        self._logger.debug(f"Set power to {self._power}")
        pass

    def get_power(self):
        return self._power


class PwmFan(Fan):
    """A class the represent a PWM controlled fan"""

    def __init__(self, logger, pwm_pin, pwm_frequency):
        self._logger = logger
        self._frequency = pwm_frequency
        self._pin = pwm_pin
        self._pi = pigpio.pi() 

        if not self._pi.connected:
            self._logger.error("Error connectiong to pigpio")

        self._pi.hardware_PWM(self._pin, pwm_frequency, 0)
        self._pi.set_PWM_range(self._pin, 100)

    def destroy(self):
        self._pi.stop()
        
    def set_power(self, power):
        assert power >= 0
        assert power <= 1

        self._power = power
        self._pi.set_PWM_dutycycle(self._pin, int(self._power * 100))


    def get_power(self):
        return self._power
