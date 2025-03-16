import pigpio
import time
import glob
from os.path import basename

from RPi import GPIO

# GPIO.setmode(GPIO.BCM)
# GPIO.setup(18, GPIO.OUT)
# GPIO.setup(23, GPIO.OUT)
# GPIO.setup(24, GPIO.OUT)

# GPIO.output(23, GPIO.LOW)
# GPIO.output(24, GPIO.LOW)

# p = GPIO.PWM(18, 25000)
# p.start(0)
# p.ChangeDutyCycle(0)

# pi = pigpio.pi()

# range = 1000000
# pi.hardware_PWM(18, 25000, int(0.2 * range))

# pi.set_pull_up_down(23, pigpio.PUD_OFF)
# pi.set_pull_up_down(24, pigpio.PUD_OFF)

# pi.set_mode(23, pigpio.OUTPUT)
# pi.set_mode(24, pigpio.OUTPUT)

# pi.write(23, 1)  # This is it
# pi.write(24, 1)

# p.ChangeDutyCycle(50)
# pi.set_PWM_dutycycle(18, 50)

# pi.stop()
# p.stop()
# GPIO.cleanup()


def list_ds18b20_devices():
    base_dir = "/sys/bus/w1/devices/"
    folders = glob.glob(base_dir + "28*")
    device_names = list(map(lambda path: basename(path), folders))

    return device_names


print(list_ds18b20_devices())
