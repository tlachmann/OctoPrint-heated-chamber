# coding=utf-8
from __future__ import absolute_import
from octoprint.events import eventManager, Events
from octoprint.util import RepeatedTimer, ResettableTimer
import octoprint.plugin
from simple_pid import PID
from time import sleep

import flask
from flask_login import current_user

from octoprint_heated_chamber.fan import softwarePwmFan, hardwarePwmFan
from octoprint_heated_chamber.temperature import Ds18b20, list_ds18b20_devices
from octoprint_heated_chamber.heater import RelayHeater, RelayMode
from octoprint_heated_chamber.servo import servoVentilation

import threading

class HeatedChamberPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    _target_temperature = 0
    _current_temperature = None
    _timer = None
    _event_object = threading.Event()
    print_in_progress = None

    ##~~ StartupPlugin mixin

    def on_after_startup(self):
        self._initial = True
        self._heaterfan = None
        self._coolerfan = None
        self._heater = None
        self._temperature_sensor = None
        self._temperature_sensor_amb = None
        self._pid = None
        self._output_servoVentilation = None

        self._frequency = None
        self._temperature_threshold = None
        self._target_temperature = 0
        self._timer = None
        self._heaterPWMMode = False
        self._event_object = threading.Event()
        self._ventilationState = None
        self.print_in_progress = None

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
            
        if self._temperature_sensor_amb is not None:
            self._temperature_sensor_amb.stop()
            self._temperature_sensor_amb = None

        if self._heaterfan is not None:
            self._heaterfan.set_power(0)
            self._heaterfan.destroy()
        if self._coolerfan is not None:
            self._coolerfan.set_power(0)
            self._coolerfan.destroy()

        if self._heater is not None:
            if not self._heaterPWMMode: ## Relay controlled Heater
                self._heater.turn_off()
            else:          ## PWM cotntroled Heater
                self._heater.set_power(0)         
                self._heater.destroy()

        if self._pid is not None:
            self._pid = None
        
        if self._output_servoVentilation is not None:
            self._output_servoVentilation.idle()
            self._output_servoVentilation.destroy()     


        return octoprint.plugin.ShutdownPlugin.on_shutdown(self)

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return dict(
            frequency=10.0,
            temperature_threshold=2.5,
            pid=dict(kp=5, kd=-0.05, ki=0.02, sample_time=10),
            heaterfan=dict(pwm=dict(pin=24, frequency=25000, idle_power=15, hardware_PWM_enabled=0)),
            temperature_sensor=dict(ds18b20=dict(frequency=1.0, device_id="28-0000057065d7")),
            temperature_sensor_amb=dict(ds18b20=dict(frequency=1.0, device_id="28-AA8DB8471401E5")),
            heater=dict(relay=dict(pin=25, relay_mode=0, heaterPWMMode=0)),
            coolerfan=dict(pwm=dict(pin=19, frequency=25000, idle_power=15, hardware_PWM_enabled=1)),
            ServoVentilation=dict(
                input=dict(pin=6, close_opening=2500, idle_opening=1500, open_opening=700), 
                output=dict(pin=7, close_opening=2500, idle_opening=1500, open_opening=700)), 
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
        try:
            #self._logger.debug(f"Original parsed_temperatures={parsed_temperatures}")
            target_temperature = 0  # 0 means off for the preheat plugin
            if self._target_temperature:
                target_temperature = self._target_temperature
            #else:
            #    target_temperature = 0
            #self._logger.debug(f"Enriched Callback self._temperature_sensor.is_running()={self._temperature_sensor.is_running()}")
            if self._current_temperature is not None:
                chamber_temp = self._current_temperature
            elif self._temperature_sensor.is_running() and self._current_temperature is None:
                self._event_set = self._event_object.wait(5)
                if self._event_set:
                    chamber_temp = self._current_temperature
                else:                    
                    return   
            elif not self._temperature_sensor.is_running():
                self._logger.debug(f"Enriched Callback self._temperature_sensor running? = {self._temperature_sensor.is_running()}")
                chamber_temp=-1
                
            parsed_temperatures["C"] = (
                chamber_temp,
                target_temperature,
            )


            #self._logger.debug(f"Enrich Callback: self._timer={self._timer}")
            if not self._timer.is_alive():
                self._logger.warn(f"Enrich Callback: self._timer not alive, timer-reset")
                self.reset()
            
            

            return parsed_temperatures
        
        except AttributeError as e:
            self._logger.warn(f"AttributeError: Plugin initilaization finished?: {e}")
            '''parsed_temperatures["C"] = (
                -2,
                -2,
            )
            return parsed_temperatures'''
        
        except TypeError as e:
            self._logger.warn(f"AttributeError: Plugin initilaization finished?: {e}")
            '''parsed_temperatures["C"] = (
                -3,
                -3,
            )
            return parsed_temperatures'''
            
        except Exception as ex: self._logger.warn(f"Enrich Exception: {ex}")
        
        
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
            target_temperature = float(cmd[cmd.index("S") + 1 :])

            # 0 means no target temp
            if target_temperature == 0 and self.print_in_progress:
                target_temperature = 28

            self._logger.info(f"Detected target_temperature={target_temperature}")
            self.set_target_temperature(target_temperature)

            return None
        

    ##~~ Plugin logic

    def _loop(self):
        try:
            target_temperature = self._target_temperature
            #self._logger.debug(f"Loop: target_temperature={target_temperature}, self._target_temperature={self._target_temperature}")+
            self._event_object.clear()
            self._current_temperature = None
            self._current_temperature = self._temperature_sensor.get_temperature()
            self._current_temperature_amb = None
            self._current_temperature_amb = self._temperature_sensor_amb.get_temperature()
            self._event_object.set()
            if self.print_in_progress:
                self._logger.debug(
                    f"LOOP: current_temperature={self._current_temperature }, target_temperature={target_temperature}, LOOP: current Printstate={self.print_in_progress },  current Ambient Temberature={self._current_temperature_amb } "
                )
                
            #### Enable Control Logic for HEATING if a target temperatur is set ####
                           
            if target_temperature is not None: # Running Heating cooling Logic

                    #### HEATERFAN Control Logic ####
                if target_temperature > 40:              
                    new_value = self._pid(self._current_temperature)
                    self._coolerfan.set_power(0)    
                    ## close Iris
                    if self._ventilationState != "close":
                        self._output_servoVentilation.set_open(self._output_servo_close_opening)
                        self._ventilationState = "close"
                    #HeaterFan: Min to Idle, above idle Fanspeed is set by PID result, 0No Heater Fan Off
                    
                    if 0 < new_value < self._pwm_heaterfan_idle_power:
                        self._heaterfan.set_power(self._pwm_heaterfan_idle_power)
                    elif new_value > self._pwm_heaterfan_idle_power:
                        self._heaterfan.set_power(new_value)
                    #elif not self.print_in_progress and self._current_temperature >= 50:
                    #    self._heaterfan.set_power(self._pwm_heaterfan_idle_power) 
                    else:
                        self._heaterfan.set_power(0)

                    #### HEATER Control Logic ####
                                    
                    if not self._heaterPWMMode:
                        if not self._heater.state() and self._current_temperature  < (
                            target_temperature - self._temperature_threshold
                        ):
                            self._heater.turn_on()
                            #self._pid.set_auto_mode(False)
                        elif self._heater.state() and self._current_temperature  >= target_temperature:
                            self._heater.turn_off()
                            #self._pid.set_auto_mode(True)
                    else:
                        ### PWM Heater Control ###
                        self._heater.set_power(new_value)
                                
                        
                #### COOLERFAN Control Logic ####
                elif self.print_in_progress and target_temperature <= 25:
                    new_value = self._pid(self._current_temperature - self._current_temperature_amb)
                    #self.set_target_temperature(30)
                    self._logger.debug(f"_loop Cooling new_value= {new_value}")
                    
                     
                    if self._ventilationState !=  "open":
                        self._output_servoVentilation.set_open(self._output_servo_open_opening)
                        self._ventilationState = "open"
                
                    # Cooling PID Values are negative (-100 to 0)
                    if new_value < 0:
                        coolingValue = abs(new_value)
                        if 0 < coolingValue < self._pwm_coolerfan_idle_power:
                            self._coolerfan.set_power(self._pwm_coolerfan_idle_power)
                        elif coolingValue > self._pwm_coolerfan_idle_power:
                            self._coolerfan.set_power(coolingValue)
                    else:
                        self._coolerfan.set_power(0)                      

                else:
                    if self._heaterfan.get_power() > 0: 
                        if self._current_temperature > 50: ### Safe Cooling Down Heater element ###
                            self._heaterfan.set_power(self._pwm_heaterfan_idle_power)
                        else:
                            self._heaterfan.set_power(0) 
                            
                    if not self._heaterPWMMode: ## Relay controlled Heater
                        if self._heater.state(): self._heater.turn_off()       
                    else: 
                        if self._heater.get_power() > 0: self._heater.set_power(0)
                        
                    if self._coolerfan.get_power() > 0: self._coolerfan.set_power(0)
                    
                    if self._ventilationState !=  "idle":
                        self._output_servoVentilation.set_open(self._output_servo_idle_opening)
                        self._ventilationState = "idle"                 
                            
                        
                              
            #### disable control logic  and shutting down devices        
            else:   
                ## Heater Handling ##
                if not self._heaterPWMMode: ## Relay controlled Heater
                    self._heater.turn_off()
                else:                       ## PWM cotntroled Heater
                    self._heater.set_power(0)
                
                ## cool down chamber and heater ##
                if self._current_temperature > (self._current_temperature_amb + 30.0): ## let heaterfan running to cool down element before switch off heater fan
                    self._heaterfan.set_power(20) 
                    if self._ventilationState !=  "open":
                        self._output_servoVentilation.set_open(self._output_servo_open_opening)
                        self._ventilationState = "open"
                    self._coolerfan.set_power(20) 
                    
                    
                        
                        
                elif self._current_temperature <= (self._current_temperature_amb + 10.0): ## let heaterfan running to cool down element before switch off heater fan
                    self._heaterfan.set_power(0)
                    ## Servo Handling              
                    if self._ventilationState !=  "idle":
                        self._output_servoVentilation.set_open(self._output_servo_idle_opening)
                        self._ventilationState = "idle"
                    ## Coolerfan handling ##
                    self._coolerfan.set_power(0) 
                
                else:
                    self._heaterfan.set_power(0)
                    
            if self._heater.state() or self._ventilationState != "idle" or self._coolerfan.get_power() > 0 or self._heaterfan.get_power() > 0:
                self._logger.info(f"LOOP: Heater State:{self._heater.state()}, HeaterFan Power={self._heaterfan.get_power()}, ServoVentialtion State={self._ventilationState}, Cooling Fan Power={self._coolerfan.get_power()}")
            
            
        except Exception as ex:
            if not self._heaterPWMMode: ## Relay controlled Heater
                self._heater.turn_off()
            else:                       ## PWM cotntroled Heater
                self._heater.set_power(0)
            self._logger.warn(f"_loop Exception: {ex}")
            if self._timer.is_alive():
                self._logger.debug(f"_loop Exception: self._timer is alive")
            else:
                self._logger.warn(f"_loop Exception: self._temperature_sensor not alive, function-reset")
                self.reset()
                
                
    def reset(self):
        ### HeaterFan
        if self._heaterfan is not None:
            self._heaterfan.idle()
            self._heaterfan.destroy()
                       
        pwm_heaterfan_pin = self._settings.get_int(["heaterfan", "pwm", "pin"], merged=True)
        pwm_heaterfan_frequency = self._settings.get_int(
            ["heaterfan", "pwm", "frequency"], merged=True
        )  
        self._pwm_heaterfan_idle_power = self._settings.get_float(
            ["heaterfan", "pwm", "idle_power"], merged=True
        )
        self._pwm_heaterfan_hardware_PWM_enabled = self._settings.get_int(
            ["heaterfan", "pwm", "hardware_PWM_enabled"], merged=True
        )

        if self._pwm_heaterfan_hardware_PWM_enabled:
            self._heaterfan = hardwarePwmFan(
                self._logger, pwm_heaterfan_pin, pwm_heaterfan_frequency, self._pwm_heaterfan_idle_power
            )
        else:
            self._heaterfan = softwarePwmFan(
                self._logger, pwm_heaterfan_pin, pwm_heaterfan_frequency, self._pwm_heaterfan_idle_power
            )
        if self._initial: 
            self._heaterfan.set_power(100)
            sleep(2)
            self._heaterfan.set_power(0)
            sleep(2)

            
        self._heaterfan.idle()


        ### CoolerFan
        if self._coolerfan is not None:
            self._coolerfan.idle()
            self._coolerfan.destroy()
            
        pwm_coolerfan_pin = self._settings.get_int(["coolerfan", "pwm", "pin"], merged=True)
        pwm_coolerfan_frequency = self._settings.get_int(
            ["coolerfan", "pwm", "frequency"], merged=True
        )
        self._pwm_coolerfan_idle_power = self._settings.get_float(
            ["coolerfan", "pwm", "idle_power"], merged=True
        )
        self._pwm_coolerFan_hardware_PWM_enabled = self._settings.get_int(
            ["coolerfan", "pwm", "hardware_PWM_enabled"], merged=True
        )
        '''
        self._pwm_coolerfan_cooling_targettemp = self._settings.get_int(
            ["coolerfan", "pwm", "cooling_targettemp"], merged=True
        )
        '''
        #self.coolerfan.set_power = 25.0
        
        
        if self._pwm_coolerFan_hardware_PWM_enabled:
            self._coolerfan = hardwarePwmFan(
                self._logger, pwm_coolerfan_pin, pwm_coolerfan_frequency, self._pwm_coolerfan_idle_power
            )
        else:
            self._coolerfan = softwarePwmFan(
                self._logger, pwm_coolerfan_pin, pwm_coolerfan_frequency, self._pwm_coolerfan_idle_power
            )
        if self._initial: 
            self._coolerfan.set_power(100)
            sleep(2)
            self._coolerfan.set_power(0)
            sleep(2)

                        
        self._coolerfan.idle()
        
        
        ### Servo Ventilation
        if self._output_servoVentilation is not None:
            self._output_servoVentilation.idle()
            self._output_servoVentilation.destroy()
            
        
        output_servo_pin = self._settings.get_int(["ServoVentilation", "output", "pin"], merged=True)
        
        self._output_servo_idle_opening = self._settings.get_float(
            ["ServoVentilation", "output", "idle_opening"], merged=True
        )
        self._output_servo_close_opening = self._settings.get_int(
            ["ServoVentilation", "output", "close_opening"], merged=True
        )
        self._output_servo_open_opening = self._settings.get_int(
            ["ServoVentilation", "output", "open_opening"], merged=True
        )
        

        
        '''
        output_servo_pin = 7
        self._output_servo_idle_opening = 500
        self._output_servo_close_opening = 2500    
        self._output_servo_open_opening = 500
        '''
        self._output_servoVentilation = servoVentilation(
            self._logger, output_servo_pin, self._output_servo_idle_opening
        )

        #self._output_servoVentilation.idle()   
    
        if self._initial: 
            self._output_servoVentilation.set_open(self._output_servo_close_opening)
            sleep(2)
            self._output_servoVentilation.set_open(self._output_servo_open_opening)
            sleep(2)


        
        self._output_servoVentilation.set_open(self._output_servo_idle_opening)
        self._ventilationState = "idle"
        
    
        # Temperature sensor
        if self._temperature_sensor is not None:
            self._temperature_sensor.stop()

        temperature_sensor_ds18b20_frequency = self._settings.get_float(
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

        # Temperature sensor _Ambient
        if self._temperature_sensor_amb is not None:
            self._temperature_sensor_amb.stop()

        temperature_sensor_amb_ds18b20_frequency = self._settings.get_float(
            ["temperature_sensor_amb", "ds18b20", "frequency"], merged=True
        )
        temperature_sensor_amb_ds18b20_device_id = self._settings.get(
            ["temperature_sensor_amb", "ds18b20", "device_id"], merged=True
        )
        self._temperature_sensor_amb = Ds18b20(
            self._logger,
            temperature_sensor_amb_ds18b20_frequency,
            temperature_sensor_amb_ds18b20_device_id,
        )
        self._temperature_sensor_amb.start()
        # Heater

        if self._heater is not None:
            self._heater.turn_off()
            self._heater.destroy()

        heater_pin = self._settings.get_int(["heater", "relay", "pin"], merged=True)
        heater_relay_mode = RelayMode(
            self._settings.get_int(["heater", "relay", "relay_mode"], merged=True)
        )
        self._heaterPWMMode = self._settings.get_int(
            ["heater", "relay", "heaterPWMMode"], merged=True
        )
        
        self._heater = RelayHeater(self._logger, heater_pin, heater_relay_mode, self._heaterPWMMode)
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
                -100,
                100,
            )
        else:
            self._pid = PID(
                pid_kp,
                pid_kd,
                pid_ki,
                sample_time=pid_sample_time,
            )
            self._pid.output_limits = (
                -100,
                100,
            )
        self._logger.debug(
            f"RESET: self._target_temperature={self._target_temperature}"
        )
        if self._target_temperature is not None:
            self._pid.setpoint = self._target_temperature
            
            #    self._pid.set_auto_mode(True)
            #else:
            #    self._pid.set_auto_mode(True)

        # Timer
        self._frequency = self._settings.get_float(["frequency"], merged=True)
        if self._timer:
            self._timer.cancel()
            self._timer = None
            
        self._logger.debug(f"RESET: pre Timer setup self._timer={self._timer}")
        self._timer = RepeatedTimer(self._frequency, self._loop, args=None, kwargs=None, daemon=True) #, run_first=True , on_reset=self.reset
        self._logger.debug(f"RESET: post Timer setup self._timer={self._timer}")
        self._timer.start()
        self._logger.debug(f"RESET: pre start timer self._timer={self._timer}")


        # Misc
        self._temperature_threshold = self._settings.get_float(
            ["temperature_threshold"], merged=True
        )
        
        self._initial = False
        
        
        
        

    def set_target_temperature(self, target_temperature):
        self._target_temperature = target_temperature
        self._logger.info(
            f"Set target chamber temperature to: {self._target_temperature}"
        )

        if self._target_temperature is not None:
        
            self._pid.setpoint = self._target_temperature
            self._logger.debug(
                f"Set PID Setpoint: {self._target_temperature}"
                )
            #    self._pid.set_auto_mode(True)
            #else:
            #    self._pid.set_auto_mode(True)




    # ~~ EventPlugin mixin
    def on_event(self, event, payload):
        if event == Events.CONNECTED:
            self._logger.debug("on_event: Events.CONNECTED")
            #self.conneted = True
            #self.update_ui()

        #if event == Events.CLIENT_OPENED:
            # self.update_ui()
        
        if event == Events.PRINT_RESUMED:
            self._logger.debug("on_event: Events.PRINT_RESUMED. previous status: self.print_in_progress= %s", self.print_in_progress)
            self.print_in_progress = True
             # self.update_ui()
           
        if event == Events.PRINT_STARTED:
            self._logger.debug("on_event: Events.PRINT_STARTED. previous status: self.print_in_progress= %s", self.print_in_progress)
            self.print_in_progress = True
            #self.run_tasks()
            #self.update_ui()

        elif event == Events.PRINT_DONE:
            self._logger.debug("on_event: Events.PRINT_DONE. previous status: self.print_in_progress= %s", self.print_in_progress)
            self.print_in_progress = False
            self.set_target_temperature(0.0)
            #self.update_ui()

        elif event in (Events.PRINT_CANCELLED, Events.PRINT_FAILED):
            self._logger.debug("on_event: Events.PRINT_CANCELLED or Events.PRINT_FAILED. previous status: self.print_in_progress= %s", self.print_in_progress)
            self.print_in_progress = False
            self.set_target_temperature(0.0)
            #self.run_tasks()

        if event in (Events.ERROR, Events.DISCONNECTED):
            self._logger.debug("on_event: Events.ERROR or Events.DISCONNECTED. previous status: self.print_in_progress= %s", self.print_in_progress)
            self._logger.info("Detected Error or Disconnect in %s will call listeners for shutdown_on_error!", event)
            self.print_in_progress = False
            self.set_target_temperature(0.0)
            #self.run_tasks()

        if event == Events.PRINTER_STATE_CHANGED:
            if "error" in payload["state_string"].lower():
                self._logger.debug("on_event: Events.PRINTER_STATE_CHANGED. previous status: self.print_in_progress= %s", self.print_in_progress)
                self._logger.info("Detected Error in %s id: %s state: %s  will call listeners for shutdown_on_error!", event, payload["state_id"], payload["state_string"])
                self.print_in_progress = False
                self.set_target_temperature(0.0)
                #self.run_tasks()



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
