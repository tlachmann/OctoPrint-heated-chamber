# coding=utf-8
from __future__ import absolute_import
from octoprint.util import RepeatedTimer
import octoprint.plugin
from simple_pid import PID

import flask
from flask_login import current_user

from octoprint_heated_chamber.fan import PwmFan
from octoprint_heated_chamber.temperature import Ds18b20, list_ds18b20_devices
from octoprint_heated_chamber.heater import RelayHeater, RelayMode


class HeatedChamberPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.TemplatePlugin,
):
    ##~~ StartupPlugin mixin

    def on_after_startup(self):
        self._fan = None
        self._heater = None
        self._temperature_sensor = None
        self._pid = None

        self._frequency = None
        self._temperature_threshold = None
        self._target_temperature = None
        self._timer = None

        self.reset()
        return octoprint.plugin.StartupPlugin.on_after_startup(self)

    ##~~ ShutdownPlugin mixin

    def on_shutdown(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        if self._temperature_sensor is not None:
            self._temperature_sensor.stop()
            self._temperature_sensor = None

        if self._fan is not None:
            self._fan.destroy()

        if self._heater is not None:
            self._heater.destroy()

        if self._pid is not None:
            self._pid = None

        return octoprint.plugin.ShutdownPlugin.on_shutdown(self)

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return dict(
            frequency=1.0,
            temperature_threshold=2.5,
            pid=dict(kp=-5, kd=-0.05, ki=-0.02, sample_time=5),
            fan=dict(pwm=dict(pin=18, frequency=25000, idle_power=15)),
            temperature_sensor=dict(
                ds18b20=dict(frequency=1.0, device_id="28-0000057065d7")
            ),
            heater=dict(relay=dict(pin=23, relay_mode=0)),
        )

    def get_settings_version(self):
        return 1

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        self._logger.debug(f"Settings saved: {data}")
        self.reset()

        return data

    def on_settings_load(self):
        data = octoprint.plugin.SettingsPlugin.on_settings_load(self)

        self._logger.debug(f"Settings loaded: {data}")

        return data

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/heated-chamber.js"],
            "css": ["css/heated-chamber.css"],
            "less": ["less/heated-chamber.less"],
        }

    ##~~ SimpleApiPlugin mixin

    def on_api_get(self, request):
        if current_user.is_anonymous():
            return "Insufficient rights", 403

        if len(request.values) != 0:
            action = request.values["action"]

            # deceide if you want the reset function in you settings dialog
            if "listDs18b20Devices" == action:
                return flask.jsonify(list_ds18b20_devices())

    ##~~ TemplatePlugin mixin

    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=False)]

    ##~~ softwareupdate.check_config hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "HeatedChamber": {
                "displayName": "Heated chamber",
                "displayVersion": self._plugin_version,
                # version check: github repository
                "type": "github_release",
                "user": "filosganga",
                "repo": "OctoPrint-heated-c hamber",
                "current": self._plugin_version,
                # update method: pip
                "pip": "https://github.com/filosganga/OctoPrint-heated-chamber/archive/{target_version}.zip",
            }
        }

    ##~~ temperatures.received hook

    def enrich_temperatures(self, comm_instance, parsed_temperatures, *args, **kwargs):
        self._logger.debug(f"Original parsed_temperatures={parsed_temperatures}")

        target_temperature = 0  # 0 means off for the preheat plugin
        if self._target_temperature is not None:
            target_temperature = self._target_temperature

        parsed_temperatures["C"] = (
            self._temperature_sensor.get_temperature(),
            target_temperature,
        )

        self._logger.debug(f"Enriched parsed_temperatures={parsed_temperatures}")

        return parsed_temperatures

    ##~~ gcode.queuing hook

    def detect_m141_m191(
        self,
        comm_instance,
        phase,
        cmd,
        cmd_type,
        gcode,
        subcode=None,
        tags=None,
        *args,
        **kwargs,
    ):
        # chamber temp can be set either via M141 or M191
        if gcode and (gcode == "M141" or gcode == "M191"):
            target_temperature = int(cmd[cmd.index("S") + 1 :])

            # 0 means no target temp
            if target_temperature == 0:
                target_temperature = None

            self._logger.debug(f"Detected target_temperature={target_temperature}")
            self.set_target_temperature(target_temperature)

            return None

    ##~~ Plugin logic

    def _loop(self) -> None:
        target_temperature = self._target_temperature

        if target_temperature is not None:
            current_temperature = self._temperature_sensor.get_temperature()
            new_value = self._pid(current_temperature)

            self._logger.debug(
                f"current_temperature={current_temperature}, target_temperature={target_temperature}, new_value={new_value}, pid={self._pid.components}"
            )

            if not self._heater.state() and current_temperature < (
                target_temperature - self._temperature_threshold
            ):
                self._heater.turn_on()
                self._pid.set_auto_mode(False)
            elif self._heater.state() and current_temperature > (
                target_temperature + self._temperature_threshold
            ):
                self._heater.turn_off()
                self._pid.set_auto_mode(True)

            self._fan.set_power(new_value)
        else:
            self._heater.turn_off()
            self._fan.idle()

    def reset(self):
        # Fan
        if self._fan is not None:
            self._fan.idle()
            self._fan.destroy()

        pwm_fan_pin = self._settings.get_int(["fan", "pwm", "pin"], merged=True)
        pwm_fan_frequency = self._settings.get_int(
            ["fan", "pwm", "frequency"], merged=True
        )
        pwm_fan_idle_power = self._settings.get_float(
            ["fan", "pwm", "idle_power"], merged=True
        )
        self._fan = PwmFan(
            self._logger, pwm_fan_pin, pwm_fan_frequency, pwm_fan_idle_power
        )
        self._fan.idle()

        # Temperature sensor
        if self._temperature_sensor is not None:
            self._temperature_sensor.stop()

        temperature_sensor_ds18b20_frequency = self._settings.get_int(
            ["temperature_sensor", "ds18b20", "frequency"], merged=True
        )
        temperature_sensor_ds18b20_device_id = self._settings.get(
            ["temperature_sensor", "ds18b20", "device_id"], merged=True
        )
        self._temperature_sensor = Ds18b20(
            self._logger,
            temperature_sensor_ds18b20_frequency,
            temperature_sensor_ds18b20_device_id,
        )
        self._temperature_sensor.start()

        # Heater

        if self._heater is not None:
            self._heater.turn_off()
            self._heater.destroy()

        heater_pin = self._settings.get_int(["heater", "relay", "pin"], merged=True)
        heater_relay_mode = RelayMode(
            self._settings.get_int(["heater", "relay", "relay_mode"], merged=True)
        )
        self._heater = RelayHeater(self._logger, heater_pin, heater_relay_mode)
        self._heater.turn_off()

        # PID

        pid_kp = self._settings.get_float(["pid", "kp"], merged=True)
        pid_kd = self._settings.get_float(["pid", "kd"], merged=True)
        pid_ki = self._settings.get_float(["pid", "ki"], merged=True)
        pid_sample_time = self._settings.get_float(["pid", "sample_time"], merged=True)

        if self._pid is not None:
            self._pid.Kp = pid_kp
            self._pid.Ki = pid_kd
            self._pid.Kd = pid_ki
            self._pid.sample_time = pid_sample_time
            self._pid.output_limits = (
                self._fan.get_idle_power(),
                self._fan.get_max_power(),
            )
        else:
            self._pid = PID(
                pid_kp,
                pid_kd,
                pid_ki,
                sample_time=pid_sample_time,
            )

        if self._target_temperature is not None:
            self._pid.setpoint = self._target_temperature
            self._pid.set_auto_mode(True)
        else:
            self._pid.set_auto_mode(False)

        # Timer
        self._frequency = self._settings.get_float(["frequency"], merged=True)
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        self._timer = RepeatedTimer(self._frequency, self._loop, daemon=True)
        self._timer.start()

        # Misc
        self._temperature_threshold = self._settings.get_float(
            ["temperature_threshold"], merged=True
        )

    def set_target_temperature(self, target_temperature):
        self._target_temperature = target_temperature
        self._logger.info(
            f"Set target chamber temperature to: {self._target_temperature}"
        )

        if self._target_temperature is not None:
            self._pid.setpoint = self._target_temperature
            self._pid.set_auto_mode(True)
        else:
            self._pid.set_auto_mode(False)


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Heated chamber"


# Set the Python version your plugin is compatible with below. Recommended is Python 3 only for all new plugins.
# OctoPrint 1.4.0 - 1.7.x run under both Python 3 and the end-of-life Python 2.
# OctoPrint 1.8.0 onwards only supports Python 3.
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = HeatedChamberPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.temperatures.received": __plugin_implementation__.enrich_temperatures,
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.detect_m141_m191,
    }
