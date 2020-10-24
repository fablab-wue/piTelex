#!/usr/bin/python3
"""
Telex Device - Button and LED controls for Rasperry Pi (Zero W)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

#https://www.programcreek.com/python/example/93338/pigpio.pi

import os
import time
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html   pip install pigpio

import log

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;43m<'+text+'>\033[0m', level)

if os.name == 'nt':   # debug on windows PC
    REMOTE_IP = '10.0.0.40'   # IP of the remote RPi with its GPIO
else:
    REMOTE_IP = None   # GPIO on this RPi itself

pi = pigpio.pi(REMOTE_IP)
if not pi.connected:
    raise Exception('no connection to remote RPi')

# init GPIOs
pi.set_pad_strength(0, 8)

def pi_exit():
    if pi:
        pi.stop()

#######

class LED_PWM():
    ''' Handle a LED connected to GPIO. LED connected to GND '''
    def __init__(self, pin):
        #super().__init__()

        self._pin = pin
        self._dst = 0
        self._val = 0
        self._prv = -1
        pi.set_mode(pin, pigpio.OUTPUT)   # output
        pi.write(pin, 0)   # off
        pi.set_PWM_frequency(pin, 200)   # 200Hz
        pi.set_PWM_range(pin, 400)   # 0...20²
        pi.set_PWM_dutycycle(pin, 0)   # off

    def __del__(self):
        #pi.set_PWM_dutycycle(self._pin, 0)   # off
        pass

    def process_fade(self):
        if self._val > self._dst:
            self._val -= 1
        if self._val < self._dst:
            self._val += 1
        val = self._val
        if val < 0:
            val = 0
        if val > 20:
            val = 20
        if self._prv != val:
            self._prv = val
            pi.set_PWM_dutycycle(self._pin, val*val)   # output with gamma

    def set_fade_dest(self, dst:int, val:int=None):
        self._dst = dst
        if self._val is not None:
            self._val = val

    def set_fade_value(self, val:int):
        self._val = val

    def add_fade_value(self, val:int):
        self._val += val
        if self._val > 40:
            self._val = 40
        if self._val < -20:
            self._val = -20

#######

class LED():
    ''' Handle a LED connected to GPIO. LED connected to GND '''
    def __init__(self, pin):
        #super().__init__()

        self._pin = pin
        self._val = 0
        #self._prv = -1
        pi.set_mode(pin, pigpio.OUTPUT)   # output
        pi.write(pin, 0)   # off

    def __del__(self):
        pass
        #pi.write(self._pin, 0)   # off

    def value(self, val:bool=None):
        if val is None:
            return self._val
        self._val = val
        pi.write(self._pin, val)

    def on(self):
        self.value(True)

    def off(self):
        self.value(False)

#######

class Button():
    ''' Handle a button connected to GPIO. Buttons connected to GND and NO-mode
    callback:
        def _callback_button([self,] gpio, level, tick):
    '''
    def __init__(self, pin, callback):
        #super().__init__()

        self._pin = pin
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_UP)
        pi.set_glitch_filter(pin, 50000)   # 50ms
        time.sleep(0.1)
        #for _ in range(50000):
        #    if pi.read(self._pin):
        #        break
        self._cb = pi.callback(pin, pigpio.FALLING_EDGE, callback)

    def __del__(self):
        self._cb.cancel()   # disable

    def is_pressed(self):
        return pi.read(self._pin) == 0

#######

class NumberSwitch():
    ''' Handle a number switch (NS) connected to GPIO. Switch connected to GND and NC-mode
    callback:
        def _callback_number_switch([self,] text:str):
    '''
    def __init__(self, pin:int, callback, active_L_H:bool=False):
        #super().__init__()
        self._cb = None
        self._time_squelch = 0
        self._is_enabled = False

        self._pin = pin
        self._callback = callback
        self._active_L_H = active_L_H
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_DOWN if self._active_L_H else pigpio.PUD_UP)
        pi.set_glitch_filter(pin, 5000)   # 5ms

    def __del__(self):
        if self._cb:
            self._cb.cancel()   # disable

    def enable(self, enable:bool):
        self._set_time_squelch(0.25)
        self._is_enabled = enable
        if self._cb:
            self._cb.cancel()
            self._cb = None
        self._pulse_dial_count = 0

        if self._pin:
            if enable:
                self._cb = pi.callback(self._pin, pigpio.RISING_EDGE if self._active_L_H else pigpio.FALLING_EDGE, self._callback_pulse_dial)
                pi.set_watchdog(self._pin, 200)   # 200ms
            else:
                pi.set_watchdog(self._pin, 0)   # disable

    def _callback_pulse_dial(self, gpio, level, tick):
        if time.time() <= self._time_squelch:
            return
        if not self._is_enabled:
            return

        if level == pigpio.TIMEOUT:   # watchdog timeout
            #LOG(str(gpio)+str(level)+str(tick), 5)   # debug
            if self._pulse_dial_count:
                if self._pulse_dial_count >= 10:
                    self._pulse_dial_count = 0
                self._callback(str(self._pulse_dial_count))
                self._pulse_dial_count = 0
        elif (self._active_L_H and level == pigpio.HIGH) or (not self._active_L_H and level == pigpio.LOW):
            self._pulse_dial_count += 1
            self._callback('.')
            #print('+', end='')
        else:
            pass
            #print('$', end='')

    def _set_time_squelch(self, t_diff:float):
        t = time.time() + t_diff
        if self._time_squelch < t:
            self._time_squelch = t

#######

class Observer():
    def __init__(self, pin, inv, stable_count):
        self._pin = pin
        self._inv = inv
        self._stable_count = stable_count

        self._line_stable = None
        self._counter = 0

    def process(self) -> bool:
            line = (not pi.read(self._pin)) == self._inv   # int->bool, logical xor
            if line != self._line_stable:

                self._counter += 1
                if self._counter == self._stable_count:
                    self._line_stable = line
                    #LOG('Line state change: '+str(rxd), 3)
                    return line
            else:
                self._counter = 0

    def reset(self):
        self._counter = 0

    def get_state(self) -> bool:
        return self._line_stable
