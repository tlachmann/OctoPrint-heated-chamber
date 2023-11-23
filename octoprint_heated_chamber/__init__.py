# coding=utf-8
from __future__ import absolute_import
from RPi import GPIO
from octoprint.util import RepeatedTimer

### (Don't forget to remove me)
# This is a basic skeleton for your plugin's __init__.py. You probably want to adjust the class name of your plugin
# as well as the plugin mixins it's subclassing from. This is really just a basic skeleton to get you started,
# defining your plugin as a template plugin, settings and asset plugin. Feel free to add or remove mixins
# as necessary.
#
# Take a look at the documentation on what other plugin mixins are available.

import octoprint.plugin

from octoprint_heated_chamber.fan import PwmFan
from octoprint_heated_chamber.temperature import Ds18b20
from octoprint_heated_chamber.heater import RelayHeater

class HeatedChamberPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
):
    def _loop(self) -> None:
        
        target_temperature = self._target_temperature
        printer = self._printer

        need_vacum = printer.is_printing or printer.is_pausing or printer.is_paused

        if target_temperature is not None:
            current_temperature = self._temperature_sensor.get_temperature()
            self._logger.info(f"current_temperature={current_temperature}, target_temperature={target_temperature}")
            if target_temperature - current_temperature > 2.5:
                if not self._heater.state():
                    self._heater.turn_on()

                if need_vacum:
                    self._fan.set_power(self._fan_vacum_power)
                else:
                    self._fan.set_power(self._fan_idle_power)

            elif current_temperature - target_temperature > 2.5:
                if self._heater.state():
                    self._heater.turn_off()
                power = min(round((current_temperature - target_temperature) / 10, 1), 1)
                self._fan.set_power(power)
            else:
                if self._heater.state():
                    self._heater.turn_off()

                if need_vacum:
                    self._fan.set_power(self._fan_vacum_power)
                else:
                    self._fan.set_power(self._fan_idle_power)
        else:
            self._heater.turn_off()

            if need_vacum:
                self._fan.set_power(self._fan_vacum_power)
            else:
                self._fan.set_power(self._fan_idle_power)

        self._logger.info("Looped.")
        

    def is_running(self) -> bool:
        return self._running

    ##~~ StartupPlugin mixin

    def on_startup(self, host, port):
        
        # TODO not sure this is the best place
        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)
        
        pwm_fan_pin = self._settings.get_int(['fan', 'pwm', 'pin'], merged=True)
        pwm_fan_frequency = self._settings.get_int(['fan', 'pwm', 'frequency'], merged=True)
        self._fan = PwmFan(self._logger, pwm_fan_pin, pwm_fan_frequency)
        
        temperature_sensor_ds18b20_frequency = self._settings.get_int(['temperature_sensor', 'ds18b20', 'frequency'], merged=True)
        self._temperature_sensor = Ds18b20(self._logger, temperature_sensor_ds18b20_frequency)

        heater_pin = self._settings.get_int(['heater', 'relay', 'pin'], merged=True)
        self._heater = RelayHeater(self._logger, heater_pin)

        self._running = False

        self._logger.info("Startup...")

        return octoprint.plugin.StartupPlugin.on_startup(self, host, port)

    def on_after_startup(self):
        self._target_temperature = None 
        self._fan_idle_power = self._settings.get_float(['fan', 'pwm', 'idle_power'], merged=True)
        self._fan_vacum_power = self._settings.get_float(['fan', 'pwm', 'vacum_power'], merged=True)
        
        self._temperature_sensor.start()
        self._fan.set_power(self._fan_idle_power)
        self._heater.turn_off()

        self._frequency = self._settings.get_float(['frequency'], merged=True)
        self._timer=RepeatedTimer(self._frequency, self._loop, daemon=True)
        self._timer.start()

        self._running = True
        
        self._logger.info("After Startup.")

        return octoprint.plugin.StartupPlugin.on_after_startup(self)

    def on_shutdown(self):
        
        self._timer.cancel()
        self._temperature_sensor.stop()
        self._fan.destroy()
        self._heater.destroy()

        self._logger.info("Shutdown.")

        return octoprint.plugin.ShutdownPlugin.on_shutdown(self)

    def initialize(self):
        self._logger.info("Initialize....")
        pass
    
    def on_plugin_enabled(self):
        # self._logger.info("Enabled.")
        pass
        
    def on_plugin_disabled(self):
        self._logger.info("Disabled.")

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        self._logger.info("Return default settings.")
        return dict(
            frequency=5.0, 
            fan=dict(
                pwm=dict(
                    pin=18,
                    frequency=25000,
                    idle_power=0,
                    vacum_power=0.1
                )
            ), 
            temperature_sensor=dict(
                ds18b20=dict(
                    frequency=1.
                )
            ), 
            heater=dict(
                relay=dict(
                    pin=17
                )
            )
        )

    def get_settings_version(self):
        return 1
    
    def on_settings_save(self, data):
       
       octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
       
       self._logger.info(f"Settings saved: {data}")

       return data;

    def on_settings_load(self):
        data = octoprint.plugin.SettingsPlugin.on_settings_load(self)

        self._logger.info(f"Settings loaded: {data}")

        return data;
    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/heated-chamber.js"],
            "css": ["css/heated-chamber.css"],
            "less": ["less/heated-chamber.less"],
        }

    ##~~ Softwareupdate hook

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
                "repo": "OctoPrint-HeatedChamber",
                "current": self._plugin_version,
                # update method: pip
                "pip": "https://github.com/filosganga/OctoPrint-Heatedchamber/archive/{target_version}.zip",
            }
        }

    def enrich_temperatures(self, comm_instance, parsed_temperatures, *args, **kwargs):
      self._logger.info(f"parsed_temperatures={parsed_temperatures}")
      
      target_temperature = 0 # 0 means off for the preheat plugin
      if self._target_temperature is not None:
        target_temperature = self._target_temperature
       
      parsed_temperatures["C"] = (self._temperature_sensor.get_temperature(), target_temperature)
      
      self._logger.info(f"Returning parsed_temperatures={parsed_temperatures}")
      return parsed_temperatures;

    def detect_m141_m191(self, comm_instance, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):
      # chamber temp can be set either via M141 or M191
      if gcode and (gcode == "M141" or gcode == "M191"):
        target_temp = int(cmd[cmd.index('S') + 1:])

        if target_temp == 0:
          self._target_temperature = None
        else:
          self._target_temperature = target_temp

        self._logger.info(f"Set target chamber temperature to: {self._target_temperature}")

        return None

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
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.detect_m141_m191
    }
