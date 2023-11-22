import RPi.GPIO as GPIO


class Fan:
    def set_power(self, power) -> None:
        pass

    def get_power(self) -> float:
        pass


class DummyFan(Fan):
    def __init__(self):
        self.power = 0
        pass

    def set_power(self, power) -> None:
        self.power = power
        pass

    def get_power(self):
        return self.power


class PwmFan(Fan):
    """A class the represent a PWM controlled fan"""

    def __init__(self, pwmPin, frequency):
        self.frequency = frequency
        self.pin = pwmPin

        # TODO These should be global
        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BOARD)

        GPIO.setup(self.pin, GPIO.OUT)
        self.fan = GPIO.PWM(self.pin, self.frequency)
        self.fan.start(0)

    def destroy(self):
        self.fan = None
        GPIO.cleanup(self.pin)

    def set_power(self, power):
        assert power >= 0
        assert power <= 100

        self.fan.ChangeDutyCycle(power)

    def get_power(self):
        pass
