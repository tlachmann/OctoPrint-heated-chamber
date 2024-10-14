import pigpio


class Servo:
    def set_open(self, opening) -> None:
        pass

    def get_open(self) -> float:
        pass

    def destroy(self) -> None:
        pass


class DummyServo(Servo):
    def __init__(self, logger):
        self._logger = logger
        self._opening = 0
        pass

    def set_open(self, opening) -> None:
        self._opening = opening
        self._logger.debug(f"Set opening to {self._opening}")
        pass

    def get_open(self):
        return self._opening


class servoVentilation(Servo):
    """A class the represent a PWM controlled fan"""
    #openvalue=2500
    #closeavalue=500
    def __init__(self, logger, servo_pin, idle_opening):
        self._logger = logger
        self._pin = servo_pin
        self._piServo = pigpio.pi()
        self.irisPos = None

        self._idle_opening = idle_opening
        self._lastOpening = None
        #self._heaterPWMMode = heaterPWMMode

        if not self._piServo.connected:
            self._logger.error("Error connectiong to pigpio")
        self._piServo.set_mode(self._pin, pigpio.OUTPUT) 

        self.set_open(self._idle_opening)
        

    def destroy(self):
        self._piServo.stop()

    def get_max_opening(self) -> int:
        return 100

    def get_idle_opening(self) -> int:
        return self._idle_opening

    def idle(self):  ## should be "min_on_opening" (e.g. 10%) aside function "Servo_off" (0%)
        self.set_open(self._idle_opening)

    def set_open(self, opening):
        #assert opening >= 0
        #assert opening <= 100

        self._opening = opening
        self._logger.debug(f"Set opening to {self._opening}")
        self._piServo.set_servo_pulsewidth(
            self._pin, self._opening
        )
        self._lastOpening = self._opening

    def get_open(self):
        #currentServopulses = _piServo.get_servo_pulsewidth(self._pin)
        #return currentServopulses
        return self._lastOpening