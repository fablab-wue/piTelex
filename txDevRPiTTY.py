#!/usr/bin/python3
"""
Telex Device - Serial Communication over Rasperry Pi (Zero W) to TW39 teletype

Protocol:
https://wiki.telexforum.de/index.php?title=TW39_Verfahren_(Teil_2)

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

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import log
from RPiIO import NumberSwitch, pi, pi_exit

def LOG(text:str, level:int=3):
    log.LOG('\033[30;43m<'+text+'>\033[0m', level)

#######

class TelexRPiTTY(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = '#'
        self.params = params
        self._timing_tick = 0

        self._baudrate = params.get('baudrate', 50)
        self._bytesize = params.get('bytesize', 5)
        self._stopbits = params.get('stopbits', 1.5)
        self._stopbits2 = int(self._stopbits * 2 + 0.5)

        self._pin_txd = params.get('pin_txd', 17)
        #self._inv_txd = params.get('inv_txd', False)   # not possible with PIGPIO
        self._pin_rxd = params.get('pin_rxd', 27)
        self._inv_rxd = params.get('inv_rxd', False)
        self._pin_number_switch = params.get('pin_number_switch', params.get('pin_fsg_ns', 6))   # typical connected to rxd
        self._inv_number_switch = params.get('inv_number_switch', False)
        self._pin_relay = params.get('pin_relay', 22)
        self._inv_relay = params.get('inv_relay', False)
        self._pin_dir = params.get('pin_dir', 0)
        self._pin_online = params.get('pin_online', 0)

        self._coding = params.get('coding', 0)
        self._loopback = params.get('loopback', True)
        self._observe_rxd = params.get('observe_rxd', True)
        self._timing_rxd = params.get('timing_rxd', False)

        self._tx_buffer = []
        self._rx_buffer = []
        self._rxd_stable = False   # rxd=Low
        self._rxd_counter = 0
        self._time_squelch = 0
        self._is_online = False
        self._is_enabled = False
        self._is_pulse_dial = False

        self._use_squelch = True

        # init codec
        character_duration = (self._bytesize + 1.0 + self._stopbits) / self._baudrate
        self._mc = txCode.BaudotMurrayCode(self._loopback, coding=self._coding, character_duration=character_duration)

        pi.set_mode(self._pin_rxd, pigpio.INPUT)
        pi.set_pull_up_down(self._pin_rxd, pigpio.PUD_UP)
        pi.set_glitch_filter(self._pin_rxd, 50000 // self._baudrate)   # 1ms @ 50Bd

        self._number_switch = None
        if self._pin_number_switch > 0:   # 0:keyboard pos:TW39 neg:TW39@RPiCtrl
            self._number_switch = NumberSwitch(self._pin_number_switch, self._callback_number_switch, self._inv_number_switch)

        pi.set_mode(self._pin_txd, pigpio.OUTPUT)
        #pi.write(self._pin_txd, not self._inv_txd)
        pi.write(self._pin_txd, 1)
        if self._pin_online:
            pi.set_mode(self._pin_online, pigpio.OUTPUT)
            pi.write(self._pin_online, 0)
        if self._pin_relay:
            pi.set_mode(self._pin_relay, pigpio.OUTPUT)   # relay for commutating
            pi.write(self._pin_relay, self._inv_relay)   # pos polarity
        if self._pin_dir:
            pi.set_mode(self._pin_dir, pigpio.OUTPUT)   # direction of comminication
            pi.write(self._pin_dir, 0)   # 1=transmitting

        self._set_enable(False)
        self._set_online(False)

        # init bit bongo serial read
        try:
            status = pi.bb_serial_read_close(self._pin_rxd)   # try to close if it is still open from last debug
        except:
            pass
        status = pi.bb_serial_read_open(self._pin_rxd, self._baudrate, self._bytesize)
        pi.bb_serial_invert(self._pin_rxd, self._inv_rxd)

        if self._timing_rxd:
            self._cb = pi.callback(self._pin_rxd, pigpio.EITHER_EDGE, self._callback_timing)

        # init bit bongo serial write
        self.last_wid = None

        # debug
        #cbs = pi.wave_get_max_cbs()
        #micros = pi.wave_get_max_micros()
        #pulses = pi.wave_get_max_pulses()
        #pass


    def __del__(self):
        global pi

        if pi:
            pi.bb_serial_read_close(self._pin_rxd)
            pi.wave_clear()
        super().__del__()

    # -----

    def exit(self):
        global pi

        if pi:
            pi.bb_serial_read_close(self._pin_rxd)
            del pi
            pi = None
            pi_exit()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)

    # -----

    def write(self, a:str, source:str):
        if len(a) != 1:
            self._check_commands(a)
            return

        if a == '#':
            a = '@'   # ask teletype for hardware ID

        if a:
            self._tx_buffer.append(a)

    # =====

    def idle20Hz(self):
        #time_act = time.time()

        if self._observe_rxd:
            #rxd = pi.read(self._pin_rxd)
            rxd = (not pi.read(self._pin_rxd)) == self._inv_rxd   # int->bool, logical xor
            if rxd != self._rxd_stable:

                self._rxd_counter += 1
                if self._rxd_counter == 40:   # 2sec
                    self._rxd_stable = rxd
                    LOG('Line state change: '+str(rxd), 3)
                    if not rxd:   # rxd=Low
                        self._rx_buffer.append('\x1bST')
                        pass
                    elif not self._is_enabled:   # rxd=High
                        self._rx_buffer.append('\x1bAT')
                        pass
                    pass
            else:
                self._rxd_counter = 0

        count, bb = pi.bb_serial_read(self._pin_rxd)
        LOG('.', 5)
        if count \
            and not(self._use_squelch and (time.time() <= self._time_squelch)) \
            and not self._is_pulse_dial:

            aa = self._mc.decodeBM2A(bb)

            if aa:
                for a in aa:
                    #self._check_special_sequences(a)
                    self._rx_buffer.append(a)

            self._rxd_counter = 0

    # -----

    def idle(self):
        if self._use_squelch and (time.time() <= self._time_squelch):
            return

        if self._tx_buffer:
            self._write_wave()

    # =====

    def _check_commands(self, a:str):
        enable = None

        if a == '\x1bA':
            if self._number_switch:
                self._number_switch.enable(False)
            self._is_pulse_dial = False
            self._set_online(True)
            enable = True

        if a == '\x1bZ':
            self._tx_buffer = []    # empty write buffer...
            if self._number_switch:
                self._number_switch.enable(False)
            self._is_pulse_dial = False
            self._set_online(False)
            enable = False   #self._use_dedicated_line
            if not enable and self._use_squelch:
                self._set_time_squelch(1.5)

        if a == '\x1bWB':
            self._set_online(True)
            if self._pin_number_switch:   # 0:keyboard pos:TW39 neg:TW39@RPiCtrl
                if self._use_squelch:
                    self._set_time_squelch(0.5)
                if self._number_switch:
                    self._number_switch.enable(True)
                self._is_pulse_dial = True
                self._tx_buffer = ['<']   # send "Bu" for 20ms pulse
                self._write_wave()
                enable = False
            else:   # dedicated line, TWM, V.10
                enable = True

        if enable is not None:
            self._set_enable(enable)

    # -----

    def _set_online(self, online:bool):
        self._is_online = online
        if self._pin_online:
            pi.write(self._pin_online, online)   # pos polarity

    # -----

    def _set_enable(self, enable:bool):
        self._is_enabled = enable
        if self._pin_relay:
            pi.write(self._pin_relay, enable != self._inv_relay)   # pos polarity
        self._mc.reset()
        if self._use_squelch:
            self._set_time_squelch(0.25)

    # -----

    def _set_time_squelch(self, t_diff:float):
        t = time.time() + t_diff
        if self._time_squelch < t:
            self._time_squelch = t

    # =====

    def _write_wave(self):
        #if (self._use_squelch and time.time() <= self._time_squelch) \
        #    or not self._tx_buffer \
        if not self._tx_buffer \
            or pi.wave_tx_busy():   # last wave is still transmitting
            return

        #a = self._tx_buffer.pop(0)
        aa = ''.join(self._tx_buffer)
        self._tx_buffer = []
        bb = self._mc.encodeA2BM(aa)
        if not bb:
            return

        #pi.wave_clear()

        if self._pin_dir:
            pi.wave_add_generic([pigpio.pulse(1<<self._pin_dir, 0, 1)]) # add dir pulse to waveform

        pi.wave_add_serial(self._pin_txd, self._baudrate, bb, 0, self._bytesize, self._stopbits2)

        if self._pin_dir:
            pi.wave_add_generic([pigpio.pulse(0, 1<<self._pin_dir, 1)]) # add dir pulse to waveform

        new_wid = pi.wave_create() # commit waveform
        pi.wave_send_once(new_wid) # transmit waveform

        if self.last_wid is not None:
            pi.wave_delete(self.last_wid) # delete no longer used waveform

        self.last_wid = new_wid

    # =====

    def _callback_number_switch(self, text:str):
        if text.isnumeric():
            self._rx_buffer.append(text)

   # -----

    def _callback_timing(self, gpio, level, tick):
        diff = tick - self._timing_tick
        self._timing_tick = tick
        if level == 0:
            text = str(diff) + '¯¯¯\\___'
        elif level == 1:
            text = str(diff) + '___/¯¯¯'
        else:
            text = '?'

        print(text, end='')

#######

