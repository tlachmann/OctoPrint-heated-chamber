import Mock.GPIO as GPIO

GPIO.setwarnings(True)
GPIO.setmode(GPIO.BOARD)


class Heater:
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
    def __init__(self, pin) -> None:
        self.pin = pin

        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    def turn_on(self) -> None:
        GPIO.output(self.pin, GPIO.HIGH)
        self.on = True

    def turn_off(self) -> None:
        GPIO.output(self.pin, GPIO.LOW)
        self.on = False

    def state(self) -> bool:
        return self.on
