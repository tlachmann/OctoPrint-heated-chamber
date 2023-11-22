# coding=utf-8
from __future__ import absolute_import

### (Don't forget to remove me)
# This is a basic skeleton for your plugin's __init__.py. You probably want to adjust the class name of your plugin
# as well as the plugin mixins it's subclassing from. This is really just a basic skeleton to get you started,
# defining your plugin as a template plugin, settings and asset plugin. Feel free to add or remove mixins
# as necessary.
#
# Take a look at the documentation on what other plugin mixins are available.

import octoprint.plugin
from octoprint_HeatedChamber.fan import DummyFan
from octoprint_HeatedChamber.temperature import Ds18b20


class HeatedchamberPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
):
    def loop(self) -> None:
        self._logger.info("Looping...")

    def is_running(self) -> bool:
        return self.running

    ##~~ StartupPlugin mixin

    def on_startup(self, host, port):
        self.running = False
        self._fan = DummyFan()
        self._temperature_sensor = Ds18b20(self._logger, 10)
        self._target_temperature = None 

        self._logger.info("Starting...")

    def on_after_startup(self):
        self._temperature_sensor.start()
        self._logger.info("Started.")

    def on_shutdown(self):
      self._logger.info("Stopping...")
      self._temperature_sensor.stop()
      self._logger.info("Stopped.")

    # def on_plugin_enabled(self):
    #     self._temperature.start()
    #     self._logger.info("Enabled.")
        
    # def on_plugin_disabled(self):
    #     self._temperature.stop()
    #     self._logger.info("Disabled.")

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return dict(frequency=5.0, fan=None, temperature_sensor=dict(ds18b20=dict(frequency=5.0)), heater=None)

    def get_settings_version(self):
        return 1

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/HeatedChamber.js"],
            "css": ["css/HeatedChamber.css"],
            "less": ["less/HeatedChamber.less"],
        }

    ##~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "HeatedChamber": {
                "displayName": "Heatedchamber Plugin",
                "displayVersion": self._plugin_version,
                # version check: github repository
                "type": "github_release",
                "user": "filosganga",
                "repo": "OctoPrint-Heatedchamber",
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
       
      parsed_temperatures["C"] = (self._temperature_sensor.temperature(), target_temperature)
      
      self._logger.info(f"Returning parsed_temperatures={parsed_temperatures}")
      return parsed_temperatures;

    def detect_m141(self, comm_instance, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):
      if gcode and gcode == "M141":
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
__plugin_name__ = "Heatedchamber Plugin"


# Set the Python version your plugin is compatible with below. Recommended is Python 3 only for all new plugins.
# OctoPrint 1.4.0 - 1.7.x run under both Python 3 and the end-of-life Python 2.
# OctoPrint 1.8.0 onwards only supports Python 3.
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = HeatedchamberPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.temperatures.received": __plugin_implementation__.enrich_temperatures,
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.detect_m141
    }
