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
from RPiIO import NumberSwitch, Observer, pi, pi_exit

#def LOG(text:str, level:int=3):
#    log.LOG('\033[30;43m<'+text+'>\033[0m', level)

#######

class TelexRPiTTY(txBase.TelexBase):
    S_IDLE = 0
    S_DIAL_PULSE = 1
    S_DIAL_KEYBOARD = 2
    S_WRITE_INIT = 3
    S_WRITE = 4

    def __init__(self, **params):
        super().__init__()

        self.id = 'piT'
        self.params = params
        self._timing_tick = 0
        self._time_EOT = 0
        self._last_waiting = 0
        self._state = None
        self._time_squelch = 0
        self._use_squelch = True

        self._tx_buffer = []
        self._rx_buffer = []

        # get setting params

        self._mode = params.get('mode', 'TW39')

        self._baudrate = params.get('baudrate', 50)
        self._bytesize = params.get('bytesize', 5)
        self._stopbits = params.get('stopbits', 1.5)
        self._stopbits2 = int(self._stopbits * 2 + 0.5)

        self._pin_txd = params.get('pin_txd', 17)
        #self._inv_txd = params.get('inv_txd', False)   # not possible with PIGPIO
        self._pin_dir = params.get('pin_dir', 0)
        self._pin_rxd = params.get('pin_rxd', 27)
        self._inv_rxd = params.get('inv_rxd', False)
        self._pin_relay = params.get('pin_relay', 22)
        self._inv_relay = params.get('inv_relay', False)
        self._pin_power = params.get('pin_power', 0)
        self._inv_power = params.get('inv_power', False)
        self._pin_number_switch = params.get('pin_number_switch', params.get('pin_fsg_ns', 6))   # pin typical wired to rxd pin
        self._inv_number_switch = params.get('inv_number_switch', False)

        self._line_observer = None
        if params.get('use_observe_line', True):
            self._pin_observe_line = params.get('pin_observe_line', self._pin_rxd)
            self._inv_observe_line = params.get('inv_observe_line', self._inv_rxd)
            self._line_observer = Observer(self._pin_observe_line, self._inv_observe_line, 10)   # 10ticks = 0.5sec

        self._coding = params.get('coding', 0)
        self._loopback = params.get('loopback', True)
        self._timing_rxd = params.get('timing_rxd', False)
        self._WB_pulse_length = params.get('WB_pulse_length', 40)

        # init codec

        self._character_duration = (self._bytesize + 1.0 + self._stopbits) / self._baudrate
        self._mc = txCode.BaudotMurrayCode(self._loopback, coding=self._coding, character_duration=self._character_duration)

        # init GPIOs

        pi.set_mode(self._pin_rxd, pigpio.INPUT)
        pi.set_pull_up_down(self._pin_rxd, pigpio.PUD_UP)
        pi.set_glitch_filter(self._pin_rxd, 50000 // self._baudrate)   # 1ms @ 50Bd

        self._number_switch = None
        if self._pin_number_switch > 0:   # 0:keyboard pos:TW39 neg:TW39@RPiCtrl
            self._number_switch = NumberSwitch(self._pin_number_switch, self._callback_number_switch, self._inv_number_switch)

        pi.set_mode(self._pin_txd, pigpio.OUTPUT)
        #pi.write(self._pin_txd, not self._inv_txd)
        pi.write(self._pin_txd, 1)
        if self._pin_power:
            pi.set_mode(self._pin_power, pigpio.OUTPUT)
            pi.write(self._pin_power, 0)
        if self._pin_relay:
            pi.set_mode(self._pin_relay, pigpio.OUTPUT)   # relay for commutating
            pi.write(self._pin_relay, self._inv_relay)   # pos polarity
        if self._pin_dir:
            pi.set_mode(self._pin_dir, pigpio.OUTPUT)   # direction of comminication
            pi.write(self._pin_dir, 0)   # 1=transmitting

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

        # init state

        self._set_state(self.S_IDLE)
        
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
        ''' called by system to get next input character '''
        if self._rx_buffer:
            return self._rx_buffer.pop(0)

    # -----

    def write(self, a:str, source:str):
        ''' called by system to output next character or sned control sequence '''
        if a == '#':
            a = '@'   # WRU - ask teletype for hardware ID (KG)
        if a:
            self._tx_buffer.append(a)

    # =====

    def idle(self):
        ''' called by system as often as possible to do background staff '''
        if not self._tx_buffer \
            or (self._use_squelch and (time.time() <= self._time_squelch)) \
            or self._is_writing_wave():
            return

        text = ''
        while self._tx_buffer \
            and len(self._tx_buffer[0]) == 1 \
            and len(text) <= 66:
            text += self._tx_buffer.pop(0)
        
        if text:
            self._write_wave(text)
        
        elif self._tx_buffer and len(self._tx_buffer[0]) > 1:   # control sequence
            a = self._tx_buffer.pop(0)
            self._check_commands(a)

    # -----

    def idle20Hz(self):
        ''' called by system every 50ms to do background staff '''
        if self._line_observer:
            line = self._line_observer.process()
            if line is True:   # rxd=High
                self._rx_buffer.append('\x1b___/¯¯¯')
                if self._state == self.S_IDLE:
                    self._rx_buffer.append('\x1bAT')
                if self._state == self.S_WRITE_INIT:
                    self._set_state(self.S_WRITE)
            elif line is False:   # rxd=Low
                self._rx_buffer.append('\x1b¯¯¯\\___')
                if self._state != self.S_IDLE:
                    self._rx_buffer.append('\x1bST')

        count, bb = pi.bb_serial_read(self._pin_rxd)
        #LOG('.', 5)
        if count \
            and not(self._use_squelch and (time.time() <= self._time_squelch)) \
            and self._state != self.S_DIAL_PULSE:

            aa = self._mc.decodeBM2A(bb)

            if aa:
                for a in aa:
                    #self._check_special_sequences(a)
                    self._rx_buffer.append(a)
                    # T68d printer is set for BU after sending WRU, set it back to Zi immediately, won't hurt on other TTYs
                    if a == '@':
                        self._tx_buffer.insert(0, '>')

            if self._line_observer:
                self._line_observer.reset()

    # -----

    def idle2Hz(self):
        ''' called by system every 500ms to do background staff '''
        # send printer FIFO info
        if self._state == self.S_WRITE:
            waiting = int((self._time_EOT - time.time()) / self._character_duration + 0.9)
            waiting += len(self._tx_buffer)   # estimation of left chars in buffer
            if waiting < 0:
                waiting = 0
            if waiting != self._last_waiting:
                self._rx_buffer.append('\x1b~' + str(waiting))
                self._last_waiting = waiting

        elif self._state == self.S_WRITE_INIT:
            if self._line_observer:
                line = self._line_observer.get_state()
                if not line:
                    self._rx_buffer.append('\x1b^')

    # =====

    def _check_commands(self, a:str):
        ''' check for control sequences and set new state '''
        if a == '\x1bZ':
            self._set_state(self.S_IDLE)
            self._tx_buffer = []    # empty write buffer...

        elif a == '\x1bWB':
            if self._mode == 'TW39':
                self._set_state(self.S_DIAL_PULSE)
            else:
                self._set_state(self.S_DIAL_KEYBOARD)

        elif a == '\x1bA':
            self._set_state(self.S_WRITE_INIT)

        elif a == '\x1bTP0':
            self._enable_power(False)

        elif a == '\x1bTP1':
            self._enable_power(True)

    # -----

    def _set_state(self, new_state:int):
        ''' set new state and change hardware propperties '''
        if self._state == new_state:
            return

        l.debug('set_state {}'.format(new_state))
        if new_state == self.S_IDLE:
            self._set_time_squelch(1.5)
            self._enable_relay(False)
            self._enable_number_switch(False)
            self._mc.reset()

        elif new_state == self.S_DIAL_PULSE:
            self._set_time_squelch(0.5)
            self._enable_relay(False)
            self._enable_number_switch(True)
            self._write_wave('§')   # special control character to send WB-pulse to FSG

        elif new_state == self.S_DIAL_KEYBOARD:
            self._set_time_squelch(0.25)
            self._enable_relay(True)
            self._enable_number_switch(False)

        elif new_state == self.S_WRITE_INIT:
            self._set_time_squelch(0.25)
            self._enable_relay(True)
            self._enable_number_switch(False)
            if not self._line_observer:
                new_state = self.S_WRITE
                self._last_waiting = -1
            if self._mode == 'V10':
                self._write_wave('%\\_')

        elif new_state == self.S_WRITE:
            self._last_waiting = -1
            pass

        self._state = new_state
        pass

    # -----

    def _enable_relay(self, enable:bool):
        ''' set GPIO for the relay '''
        if self._pin_relay:
            l.debug('enable_relay {}'.format(enable))
            pi.write(self._pin_relay, enable != self._inv_relay)   # pos polarity

    # -----

    def _enable_number_switch(self, enable:bool):
        ''' set state machine for the number switch '''
        if self._pin_number_switch:   # 0:keyboard pos:TW39 neg:TW39@RPiCtrl
            l.debug('enable_number_switch {}'.format(enable))
            if self._number_switch:
                self._number_switch.enable(enable)

    # -----

    def _enable_power(self, enable:bool):
        ''' set GPIO for the power SSR '''
        if self._pin_power:
            l.debug('enable_power {}'.format(enable))
            pi.write(self._pin_power, enable != self._inv_power)   # pos polarity

    # -----

    def _set_time_squelch(self, t_diff:float):
        ''' set time to ignore input characters and dely output characters '''
        if not self._use_squelch:
            return
        t = time.time() + t_diff
        if self._time_squelch < t:
            self._time_squelch = t

    # =====

    def _is_writing_wave(self):
        ''' is wave transmitter still transmitting '''
        return pi.wave_tx_busy()   # last wave is still transmitting

    # -----

    def _write_wave(self, text:str):
        ''' use wave transmitter to write text as baudot serial sequence '''
        if not text or self._is_writing_wave():   # last wave is still transmitting
            return
        
        #pi.wave_clear()

        if text == '§':
            if self._WB_pulse_length <= 0:
                return
            #bb = [0x11110]   # experimental: 40ms pulse  @50Bd
            pi.wave_add_generic([   # add WB-pulse with XXXms to waveform
                pigpio.pulse(0, 1<<self._pin_txd, self._WB_pulse_length * 1000),
                pigpio.pulse(1<<self._pin_txd, 0, 1)
                ])

        else:
            bb = self._mc.encodeA2BM(text)
            if not bb:
                return

            if self._pin_dir:
                pi.wave_add_generic([pigpio.pulse(1<<self._pin_dir, 0, 1)]) # add dir pulse to waveform

            pi.wave_add_serial(self._pin_txd, self._baudrate, bb, 0, self._bytesize, self._stopbits2)

            if self._pin_dir:
                pi.wave_add_generic([pigpio.pulse(0, 1<<self._pin_dir, 1)]) # add dir pulse to waveform

        new_wid = pi.wave_create() # commit waveform
        pi.wave_send_once(new_wid) # transmit waveform

        micros = pi.wave_get_micros()
        l.debug('write_wave {}chr {}ms'.format(len(text), micros/1000000))

        self._time_EOT = time.time() + micros/1000000

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

