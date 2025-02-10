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

S_SLEEPING = -10
S_OFFLINE = 0
S_DIALING_PULSE = 11
S_DIALING_KEYBOARD = 12
S_ACTIVE_INIT = 20
S_ACTIVE_READY = 21

#######

class TelexRPiTTY(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'piT'
        self.params = params
        self._timing_tick = 0
        self._time_EOT = 0
        self._state = None
        self._time_squelch = 0
        self._use_squelch = True
        self._keep_alive_counter = 0

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

        self._txd_powersave = params.get('txd_powersave', 0)

        self._pin_number_switch = params.get('pin_number_switch', 6 if self._mode not in ('V10', 'TWM', 'AGT-TWM') else 0)   # pin typical wired to rxd pin
        self._inv_number_switch = params.get('inv_number_switch', False)

        if self._inv_rxd:
            raise Exception('PIGPIO-lib does not support inverted RXD correctly on serial communication')

        self._line_observer = None
        if params.get('use_observe_line', True):
            self._pin_observe_line = params.get('pin_observe_line', self._pin_rxd)
            self._inv_observe_line = params.get('inv_observe_line', self._inv_rxd)
            self._nZZ_observe_line = params.get('nZZ_observe_line', False)
            self._line_observer = Observer(self._pin_observe_line, self._inv_observe_line, 10)   # 10ticks = 0.5sec

        self._coding = params.get('coding', 0)
        self._loopback = params.get('loopback', True)
        self._timing_rxd = params.get('timing_rxd', False)
        self._WB_pulse_length = params.get('WB_pulse_length', 40)
        self._double_WR = params.get('double_WR', False)

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
        pi.write(self._pin_txd, not self._txd_powersave)

        if self._pin_relay:
            pi.set_mode(self._pin_relay, pigpio.OUTPUT)   # relay for commutating
            pi.write(self._pin_relay, self._inv_relay)   # pos polarity
        if self._pin_dir:
            pi.set_mode(self._pin_dir, pigpio.OUTPUT)   # direction of comminication
            pi.write(self._pin_dir, 0)   # 1=transmitting

        # init bit bongo serial read

        try:
            _ = pi.bb_serial_read_close(self._pin_rxd)   # try to close if it is still open from last debug
        except:
            pass
        _ = pi.bb_serial_read_open(self._pin_rxd, self._baudrate, self._bytesize)
        pi.bb_serial_invert(self._pin_rxd, self._inv_rxd)

        if self._timing_rxd:
            self._cb = pi.callback(self._pin_rxd, pigpio.EITHER_EDGE, self._callback_timing)

        # init bit bongo serial write

        self.last_wid = None

        # init state

        self._set_state(S_SLEEPING)

        # debug
        #cbs = pi.wave_get_max_cbs()
        #micros = pi.wave_get_max_micros()
        #pulses = pi.wave_get_max_pulses()
        #pass

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
        ''' called by system to output next character or send control sequence '''
        if a:
            if a == '#':   a = '@'   # WRU - ask teletype for hardware ID (KG)
            self._tx_buffer.append(a)
            if self._double_WR and a == '\r':
                self._tx_buffer.append(a)

    # =====

    def idle(self):
        ''' called by system as often as possible to do background stuff '''
        if not self._tx_buffer \
            or (self._use_squelch and (time.monotonic() <= self._time_squelch)) \
            or self._is_writing_wave():
            return

        text = ''
        while self._tx_buffer \
            and len(self._tx_buffer[0]) == 1 \
            and len(text) <= 66:
            text += self._tx_buffer.pop(0)

        if text:
            if self._state >= S_ACTIVE_INIT:
                self._write_wave(text)
            self._keep_alive_counter = 0

        elif self._tx_buffer and len(self._tx_buffer[0]) > 1:   # control sequence
            a = self._tx_buffer.pop(0)
            if len(a) > 1 and a[0] == '\x1b':
                self._check_commands(a[1:])

    # -----

    def idle20Hz(self):
        ''' called by system every 50ms to do background stuff '''
        if self._line_observer:
            line = self._line_observer.process()
            if line is True:   # rxd=High
                self._send_control_sequence('___/¯¯¯')
                if self._nZZ_observe_line and self._state in (S_SLEEPING,):
                    pass   # ignore line if sleeping/power_saving
                elif self._state in (S_SLEEPING, S_OFFLINE):
                    self._send_control_sequence('AT')
                elif self._state == S_ACTIVE_INIT:
                    self._send_control_sequence('AA')
                    self._set_state(S_ACTIVE_READY)
            elif line is False:   # rxd=Low
                self._send_control_sequence('¯¯¯\\___')
                if self._state not in (S_SLEEPING, S_OFFLINE):
                    self._send_control_sequence('ST')

        count, bb = pi.bb_serial_read(self._pin_rxd)
        #LOG('.', 5)
        if count \
            and not(self._use_squelch and (time.monotonic() <= self._time_squelch)) \
            and self._state != S_DIALING_PULSE:

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

            self._keep_alive_counter = 0

    # -----

    def idle2Hz(self):
        ''' called by system every 500ms to do background stuff '''
        # send printer FIFO info
        waiting = int((self._time_EOT - time.monotonic()) / self._character_duration + 0.9)
        waiting += len(self._tx_buffer)   # estimation of left chars in buffer

        # Cap negative waiting times (sending finished in the past)
        if waiting < 0:
            waiting = 0

        # Send buffer updates to i-Telex when teleprinter is active.
        if self._state >= S_ACTIVE_INIT:
            self._send_control_sequence('~' + str(waiting))

        if self._state == S_ACTIVE_READY:
            self._keep_alive_counter += 1
            if self._mode == 'V10' and self._keep_alive_counter > 60:   # 30sec
                self._keep_alive_counter = 0
                self._tx_buffer.insert(0, '°')

        elif self._state == S_ACTIVE_INIT:
            if self._line_observer:
                line = self._line_observer.get_state()
                if not line:
                    self._send_control_sequence('...')

    # =====

    def _check_commands(self, a:str):
        ''' check for control sequences and set new state '''
        if a == 'ZZ':
            self._set_state(S_SLEEPING)

        elif a == 'Z':
            self._set_state(S_OFFLINE)
            self._tx_buffer = []    # empty write buffer...
            self._send_control_sequence('~0')

        elif a == 'WB':
            if self._mode in ('TW39', 'TW39H', 'AGT', 'AGT-TW39'):
                self._set_state(S_DIALING_PULSE)
            else:
                self._set_state(S_DIALING_KEYBOARD)

        elif a == 'A':
            self._set_state(S_ACTIVE_INIT)

        elif a == 'AA':
            self._set_state(S_ACTIVE_READY)

        elif a == 'TP0':
            self._enable_power(False)

        elif a == 'TP1':
            self._enable_power(True)

    # -----

    def _set_state(self, new_state:int):
        ''' set new state and change hardware propperties '''
        if self._state == new_state:
            return

        l.debug('set_state {}'.format(new_state))
        if new_state == S_SLEEPING:
            self._set_time_squelch(2.5)
            self._enable_relay(False)
            self._enable_number_switch(False)
            self._mc.reset()
            self._enable_power(False)

        elif new_state == S_OFFLINE:
            self._set_time_squelch(1.5)
            self._enable_relay(False)
            self._enable_number_switch(False)
            self._mc.reset()
            self._enable_power(True)

        elif new_state == S_DIALING_PULSE:
            self._enable_power(True)
            self._set_time_squelch(0.5)
            self._enable_relay(False)
            self._enable_number_switch(True)
            self._write_wave('§')   # special control character to send WB-pulse to FSG

        elif new_state == S_DIALING_KEYBOARD:
            self._enable_power(True)
            self._set_time_squelch(0.25)
            self._enable_relay(True)
            self._enable_number_switch(False)

        elif new_state == S_ACTIVE_INIT:
            self._enable_power(True)
            self._set_time_squelch(0.25)
            self._enable_relay(True)
            self._enable_number_switch(False)
            if self._mode == 'V10' or not self._line_observer or self._state in (S_DIALING_PULSE, S_DIALING_KEYBOARD):
                # Immediately set S_ACTIVE_READY if mode is V10, if we've been
                # dialling or line observer isn't configured. In all other
                # cases, the line observer will trigger S_ACTIVE_READY mode.
                new_state = S_ACTIVE_READY
                self._send_control_sequence('AA')

        if new_state == S_ACTIVE_READY:
            self._enable_power(True)
            if self._mode == 'V10':
                self._write_wave('%\\_')

        self._state = new_state

    # -----

    def _send_control_sequence(self, cmd:str):
        self._rx_buffer.append('\x1b'+cmd)

    # -----

    def _enable_relay(self, enable:bool):
        ''' set GPIO for the relay '''
        if not enable and self._mode == 'TW39H':
            pi.write(self._pin_txd, False)
            time.sleep(0.005)
            self._send_control_sequence('OFF')
            
        if self._pin_relay:
            l.debug('enable_relay {}'.format(enable))
            pi.write(self._pin_relay, enable != self._inv_relay)   # pos polarity

        if enable and self._mode == 'TW39H':
            time.sleep(0.005)
            pi.write(self._pin_txd, True)
            self._send_control_sequence('ON')
            
    # -----

    def _enable_number_switch(self, enable:bool):
        ''' set state machine for the number switch '''
        if self._pin_number_switch:   # 0:keyboard pos:TW39 neg:TW39@RPiCtrl
            l.debug('enable_number_switch {}'.format(enable))
            if self._number_switch:
                self._number_switch.enable(enable)

    # -----

    def _enable_power(self, enable:bool):
            l.debug('enable_power {}'.format(enable))
            if self._mode not in ('V10',):            # V.10 has no current loop, more modes affected? ('AGT...')
                pi.write(self._pin_txd, enable or not self._txd_powersave)       # loop current on / off
 
    # -----

    def _set_time_squelch(self, t_diff:float):
        ''' set time to ignore input characters and dely output characters '''
        if not self._use_squelch:
            return
        t = time.monotonic() + t_diff
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

        if text == '§':   # add WB-pulse with XXXms to waveform
            if self._WB_pulse_length <= 0:
                return

            if self._mode in ('TW39H', 'AGT', 'AGT-TW39'):   # pulse on relay-pin
                pins_to_H = 1<<self._pin_relay
                pins_to_L = 0
                if self._inv_relay:
                    pins_to_H, pins_to_L = pins_to_L, pins_to_H
            else:   # pulse on TXD-pin
                pins_to_H = 0
                pins_to_L = 1<<self._pin_txd
            pi.wave_add_generic([
                #            ON         OFF        DELAY
                pigpio.pulse(pins_to_H, pins_to_L, self._WB_pulse_length * 1000),   # send pulse
                pigpio.pulse(pins_to_L, pins_to_H, 1)                               # reset to prev. state
                ])
            self._send_control_sequence('PULSE')

        else:   # add characters as serial protocol to waveform
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

        self._time_EOT = time.monotonic() + micros/1000000

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
        diff = (diff + 500) // 1000   # us to ms
        self._timing_tick = tick
        if level == 0:
            text = str(diff) + '¯\\_'
        elif level == 1:
            text = str(diff) + '_/¯'
        else:
            text = '-?-'

        print(text, end='')

#######

