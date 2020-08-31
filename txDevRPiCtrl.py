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

import txCode
import txBase
import log
from RPiIO import Button, LED, LED_PWM, NumberSwitch, pi, pi_exit

#def LOG(text:str, level:int=3):
#    log.LOG('\033[5;30;43m<'+text+'>\033[0m', level)

#######

class TelexRPiCtrl(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = ':'
        self.params = params

        self._pin_number_switch = params.get('pin_number_switch', 0)   # connected to NS
        self._inv_number_switch = params.get('inv_number_switch', True)
        self._pin_button_1T = params.get('pin_button_1T', 0)   # single button optional
        self._pin_button_AT = params.get('pin_button_AT', 0)   # button AT optional
        self._pin_button_ST = params.get('pin_button_ST', 0)   # button ST optional
        self._pin_button_LT = params.get('pin_button_LT', 0)   # button LT optional
        self._pin_button_U1 = params.get('pin_button_U1', 0)   # button user 1 optional
        self._pin_button_U2 = params.get('pin_button_U2', 0)   # button user 2 optional
        self._pin_button_U3 = params.get('pin_button_U3', 0)   # button user 3 optional
        self._pin_button_U4 = params.get('pin_button_U4', 0)   # button user 4 optional
        self._pin_LED_A = params.get('pin_LED_A', 0)
        self._pin_LED_WB = params.get('pin_LED_WB', 0)
        self._pin_LED_WB_A = params.get('pin_LED_WB_A', 0)
        self._pin_LED_status_R = params.get('pin_LED_status_R', 0)   # LED red
        self._pin_LED_status_G = params.get('pin_LED_status_G', 0)   # LED green

        self._rx_buffer = []
        self._mode = None

        self._status_out = 0
        self._status_act = 0
        self._status_dst = 0

        self._LED_status_R = None
        self._LED_status_G = None
        if self._pin_LED_status_R and self._pin_LED_status_G:
            self._LED_status_R = LED_PWM(self._pin_LED_status_R)
            self._LED_status_G = LED_PWM(self._pin_LED_status_G)
            self._set_status('INIT')

        self._LED_A = None
        self._LED_WB = None
        self._LED_WB_A = None
        if self._pin_LED_A:
            self._LED_A = LED(self._pin_LED_A)
        if self._pin_LED_WB:
            self._LED_WB = LED(self._pin_LED_WB)
        if self._pin_LED_WB_A:
            self._LED_WB_A = LED(self._pin_LED_WB_A)

        if self._pin_button_1T:
            self._button_1T = Button(self._pin_button_1T, self._callback_button_1T)
        if self._pin_button_AT:
            self._button_AT = Button(self._pin_button_AT, self._callback_button_AT)
        if self._pin_button_ST:
            self._button_ST = Button(self._pin_button_ST, self._callback_button_ST)
        if self._pin_button_LT:
            self._button_LT = Button(self._pin_button_LT, self._callback_button_LT)

        if self._pin_button_U1:
            self._button_U1 = Button(self._pin_button_U1, self._callback_button_U1)
        if self._pin_button_U2:
            self._button_U2 = Button(self._pin_button_U2, self._callback_button_U2)
        if self._pin_button_U3:
            self._button_U3 = Button(self._pin_button_U3, self._callback_button_U3)
        if self._pin_button_U4:
            self._button_U4 = Button(self._pin_button_U4, self._callback_button_U4)

        self._number_switch = None
        if self._pin_number_switch:
            self._number_switch = NumberSwitch(self._pin_number_switch, self._callback_number_switch, self._inv_number_switch)

        self._set_mode('Z')


        # debug
        #cbs = pi.wave_get_max_cbs()
        #micros = pi.wave_get_max_micros()
        #pulses = pi.wave_get_max_pulses()
        #pass


    def __del__(self):
        super().__del__()

    # -----

    def exit(self):
        global pi

        if pi:
            del pi
            pi = None
            pi_exit()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            self._set_status('C')
            return self._rx_buffer.pop(0)

    # -----

    def write(self, a:str, source:str):
        if len(a) != 1:
            self._check_commands(a)
            return

        if a:
            #self._tx_buffer.append(a)
            self._set_status('C')

    # =====

    def idle20Hz(self):
        #time_act = time.time()

        if self._LED_status_R and self._LED_status_G:
            self._LED_status_R.process_fade()
            self._LED_status_G.process_fade()

    # -----

    def idle(self):
        pass

    # =====

    def _check_commands(self, a:str):
        if a == '\x1bA':
            self._set_mode('A')

        if a == '\x1bZ':
            self._set_mode('Z')

        if a == '\x1bWB':
            self._set_mode('WB')

    # -----

    def _set_mode(self, mode:str):
        self._mode = mode
        if mode in ['A']:
            if self._LED_A:
                self._LED_A.on()
            if self._LED_WB:
                self._LED_WB.off()
            if self._LED_WB_A:
                self._LED_WB_A.on()
            if self._number_switch:
                self._number_switch.enable(False)

        if mode in ['Z']:
            if self._LED_A:
                self._LED_A.off()
            if self._LED_WB:
                self._LED_WB.off()
            if self._LED_WB_A:
                self._LED_WB_A.off()
            if self._number_switch:
                self._number_switch.enable(False)

        if mode in ['WB']:
            if self._LED_A:
                self._LED_A.off()
            if self._LED_WB:
                self._LED_WB.on()
            if self._LED_WB_A:
                self._LED_WB_A.on()
            if self._number_switch:
                self._number_switch.enable(True)

        self._set_status(mode)

    # =====

    def _callback_button_1T(self, gpio, level, tick):
        if level == 1:
            return
        self._rx_buffer.append('\x1b1T')

    def _callback_button_AT(self, gpio, level, tick):
        if level == 1:
            return
        self._rx_buffer.append('\x1bAT')

    def _callback_button_ST(self, gpio, level, tick):
        if level == 1:
            return
        self._rx_buffer.append('\x1bST')

    def _callback_button_LT(self, gpio, level, tick):
        if level == 1:
            return
        self._rx_buffer.append('\x1bLT')

    def _callback_button_U1(self, gpio, level, tick):
        if level == 1:
            return
        text = self.params.get('text_button_U1', 'RY')
        self._rx_buffer.extend(list(text))

    def _callback_button_U2(self, gpio, level, tick):
        if level == 1:
            return
        text = self.params.get('text_button_U2', 'RY'*30)
        self._rx_buffer.extend(list(text))

    def _callback_button_U3(self, gpio, level, tick):
        if level == 1:
            return
        text = self.params.get('text_button_U3', '#')
        self._rx_buffer.extend(list(text))

    def _callback_button_U4(self, gpio, level, tick):
        if level == 1:
            return
        text = self.params.get('text_button_U4', '@')
        self._rx_buffer.extend(list(text))

    def _callback_number_switch(self, text:str):
        if text.isnumeric():
            self._rx_buffer.append(text)
            self._set_status('PE')
        else:
            self._set_status('P')

    # =====

    def _set_status(self, status:str):
        if not self._LED_status_R or not self._LED_status_G:
            return

        if status == 'Z':
            self._LED_status_R.set_fade_dest(5, 20)
            self._LED_status_G.set_fade_dest(0, 0)

        if status == 'A':
            self._LED_status_R.set_fade_dest(0, 0)
            self._LED_status_G.set_fade_dest(10, 20)

        if status == 'WB':
            self._LED_status_R.set_fade_dest(10, 20)
            self._LED_status_G.set_fade_dest(10, 20)

        if status == 'C':
            self._LED_status_R.add_fade_value(8)

        if status == 'P':
            self._LED_status_R.add_fade_value(6)
            self._LED_status_G.add_fade_value(-6)

        if status == 'PE':
            self._LED_status_R.set_fade_value(0)
            self._LED_status_G.set_fade_value(15)

        if status == 'INIT':
            self._LED_status_R.set_fade_dest(5, 25)
            self._LED_status_G.set_fade_dest(0, 25)

#######

