# OctoPrint-Heatedchamber

This plugin controls the enclosure temperature via a temperature sensor, a heater and the enclosure air extraction fan.

At the moment it only supports those:
* The DS18B20 temperature and humidity sensor
* A PWM-controlled fan
* An active-low GPIO-controlled relay heater

The settings are still a draft and not working 

## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/filosganga/OctoPrint-heated-chamber/archive/master.zip

## Configuration

You can configure the frequency at which the plugin runs the duty cycle, by default every 5 seconds.
