#!/usr/bin/python3
"""
Telex Device - Serial Communication over Rasperry Pi (Zero W) to TW39 teletype
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
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

def LOG(text:str, level:int=3):
    log.LOG('\033[30;43m<'+text+'>\033[0m', level)

if os.name == 'nt':   # debug on windows PC
    REMOTE_IP = '10.23.42.234'   # IP of the remote RPi with its GPIO
else:
    REMOTE_IP = None   # GPIO on RPi itself

pi = pigpio.pi(REMOTE_IP)
if not pi.connected:
    raise(Exception('no connection to remote RPi'))

#######

class LED_PWM():
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

#######

class Button():
    def __init__(self, pin, callback):
        #super().__init__()

        self._pin = pin
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_UP)
        pi.set_glitch_filter(pin, 50000)   # 50ms
        pi.callback(pin, pigpio.FALLING_EDGE, callback)

#######

class TelexRPiTTY(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = '#'
        self.params = params

        self._baudrate = params.get('baudrate', 50)
        self._bytesize = params.get('bytesize', 5)
        self._stopbits = params.get('stopbits', 1.5)
        self._stopbits2 = int(self._stopbits * 2 + 0.5)

        self._pin_txd = params.get('pin_txd', 17)
        self._pin_rxd = params.get('pin_rxd', 27)
        self._pin_fsg_ns = params.get('pin_fsg_ns', 6)   # connected to rxd
        self._pin_rel = params.get('pin_rel', 22)
        self._pin_dir = params.get('pin_dir', 11)
        #self._pin_oin = params.get('pin_oin', 10)
        self._pin_opt = params.get('pin_opt', 9)
        self._pin_sta = params.get('pin_sta', 23)
        self._pin_fsg_at = params.get('pin_fsg_at', 8)   # button AT optional
        self._pin_fsg_st = params.get('pin_fsg_st', 7)   # button ST optional
        self._pin_fsg_lt = params.get('pin_fsg_lt', 0)   # button LT optional
        self._pin_status_r = params.get('pin_status_r', 23)   # LED red
        self._pin_status_g = params.get('pin_status_g', 24)   # LED green

        self._inv_rxd = params.get('inv_rxd', False)
        #self._inv_txd = params.get('inv_txd', False)
        self._coding = params.get('coding', 0)
        self._loopback = params.get('loopback', True)

        self._tx_buffer = []
        self._rx_buffer = []
        self._cb = None
        self._is_pulse_dial = False
        self._pulse_dial_count = 0
        self._rxd_stable = False   # rxd=Low
        self._rxd_counter = 0
        self._time_squelch = 0
        self._is_online = False
        self._is_enabled = False
        self._is_pulse_dial = False

        self._use_pulse_dial = True
        self._use_squelch = True
        self._use_rxd_observation = True

        self._status_out = 0
        self._status_act = 0
        self._status_dst = 0

        # init codec
        character_duration = (self._bytesize + 1.0 + self._stopbits) / self._baudrate
        self._mc = txCode.BaudotMurrayCode(self._loopback, coding=self._coding, character_duration=character_duration)

        # init GPIOs
        pi.set_pad_strength(0, 8)

        pi.set_mode(self._pin_rxd, pigpio.INPUT)
        pi.set_pull_up_down(self._pin_rxd, pigpio.PUD_UP)
        pi.set_glitch_filter(self._pin_rxd, 1000)   # 1ms
        if self._pin_fsg_ns and self._pin_fsg_ns != self._pin_rxd:
            pi.set_mode(self._pin_fsg_ns, pigpio.INPUT)
            pi.set_pull_up_down(self._pin_fsg_ns, pigpio.PUD_UP)
            pi.set_glitch_filter(self._pin_fsg_ns, 1000)   # 1ms

        pi.set_mode(self._pin_txd, pigpio.OUTPUT)
        #pi.write(self._pin_txd, not self._inv_txd)
        pi.write(self._pin_txd, 1)
        pi.set_mode(self._pin_opt, pigpio.OUTPUT)
        pi.write(self._pin_opt, 0)
        pi.set_mode(self._pin_rel, pigpio.OUTPUT)   # relay for commutating
        pi.write(self._pin_rel, 0)   # pos polarity
        pi.set_mode(self._pin_dir, pigpio.OUTPUT)   # direction of comminication
        pi.write(self._pin_dir, 0)   # 1=transmitting

        if self._pin_status_r and self._pin_status_g:
            self._status_LED_r = LED_PWM(self._pin_status_r)
            self._status_LED_g = LED_PWM(self._pin_status_g)
            self.status('INIT')

        if self._pin_fsg_at:
            self._button_at = Button(self._pin_fsg_at, self._callback_button_at)
        if self._pin_fsg_st:
            self._button_st = Button(self._pin_fsg_st, self._callback_button_st)
        if self._pin_fsg_lt:
            self._button_lt = Button(self._pin_fsg_lt, self._callback_button_lt)

        self._set_enable(False)
        self._set_online(False)

        # init bit bongo serial read
        try:
            status = pi.bb_serial_read_close(self._pin_rxd)   # try to close if it is still open from last debug
        except:
            pass
        status = pi.bb_serial_read_open(self._pin_rxd, self._baudrate, self._bytesize)
        pi.bb_serial_invert(self._pin_rxd, self._inv_rxd)

        # init bit bongo serial write
        self.last_wid = None

        # debug
        #cbs = pi.wave_get_max_cbs()
        #micros = pi.wave_get_max_micros()
        #pulses = pi.wave_get_max_pulses()
        #pass


    def __del__(self):
        status = pi.bb_serial_read_close(self._pin_rxd)
        pi.wave_clear()
        super().__del__()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            self.status('C')
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
            self.status('C')

    # =====

    def idle20Hz(self):
        #time_act = time.time()

        if self._use_rxd_observation:
            rxd = pi.read(self._pin_rxd)
            rxd = (not pi.read(self._pin_rxd)) == self._inv_rxd   # int->bool, logical xor
            if rxd != self._rxd_stable:

                self._rxd_counter += 1
                if self._rxd_counter == 10:   # 0.5sec
                    self._rxd_stable = rxd
                    #LOG(str(rxd), 4)   # debug
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

        if self._status_LED_r:
            self._status_LED_r.process_fade()
            self._status_LED_g.process_fade()

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
            self._set_pulse_dial(False)
            self._set_online(True)
            enable = True
            self.status('A')

        if a == '\x1bZ':
            self._tx_buffer = []    # empty write buffer...
            self._set_pulse_dial(False)
            self._set_online(False)
            enable = False   #self._use_dedicated_line
            if not enable and self._use_squelch:
                self._set_time_squelch(1.5)
            self.status('Z')

        if a == '\x1bWB':
            self._set_online(True)
            if self._use_pulse_dial:   # TW39
                if self._use_squelch:
                    self._set_time_squelch(0.5)
                self._set_pulse_dial(True)
                self._tx_buffer = ['[']   # send 20ms pulse
                self._write_wave()
                enable = False
            else:   # dedicated line, TWM, V.10
                enable = True
            self.status('WB')

        if enable is not None:
            self._set_enable(enable)

    # -----

    def _set_online(self, online:bool):
        self._is_online = online
        pi.write(self._pin_opt, online)   # pos polarity

    # -----

    def _set_enable(self, enable:bool):
        self._is_enabled = enable
        pi.write(self._pin_rel, enable)   # pos polarity
        self._mc.reset()
        if self._use_squelch:
            self._set_time_squelch(0.5)

    # -----

    def _set_pulse_dial(self, enable:bool):
        self._is_pulse_dial = enable
        if self._cb:
            self._cb.cancel()
            self._cb = None
        self._pulse_dial_count = 0

        if self._pin_fsg_ns:
            if enable:
                self._cb = pi.callback(self._pin_fsg_ns, pigpio.FALLING_EDGE, self._callback_pulse_dial)
                pi.set_watchdog(self._pin_fsg_ns, 200)   # 200ms
            else:
                pi.set_watchdog(self._pin_fsg_ns, 0)   # disable

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

        pi.wave_add_generic([pigpio.pulse(1<<self._pin_dir, 0, 1)]) # add dir pulse to waveform

        pi.wave_add_serial(self._pin_txd, self._baudrate, bb, 0, self._bytesize, self._stopbits2)

        pi.wave_add_generic([pigpio.pulse(0, 1<<self._pin_dir, 1)]) # add dir pulse to waveform

        new_wid = pi.wave_create() # commit waveform
        pi.wave_send_once(new_wid) # transmit waveform

        if self.last_wid is not None:
            pi.wave_delete(self.last_wid) # delete no longer used waveform

        self.last_wid = new_wid

    # =====

    def _callback_pulse_dial(self, gpio, level, tick):
        if self._use_squelch and (time.time() <= self._time_squelch):
            return

        if level == pigpio.TIMEOUT:   # watchdog timeout
            LOG(str(gpio)+str(level)+str(tick), 5)   # debug
            if self._pulse_dial_count:
                if self._pulse_dial_count >= 10:
                    self._pulse_dial_count = 0
                #self._rx_buffer += str(self._pulse_dial_count)
                self._rx_buffer.append(str(self._pulse_dial_count))
                self._pulse_dial_count = 0
                self.status('PE')
        elif level == pigpio.LOW:
            self._pulse_dial_count += 1
            self.status('P')

    # -----

    def _callback_button_at(self, gpio, level, tick):
        self._rx_buffer.append('\x1bAT')

    def _callback_button_st(self, gpio, level, tick):
        self._rx_buffer.append('\x1bST')

    def _callback_button_lt(self, gpio, level, tick):
        self._rx_buffer.append('\x1bLT')

    # =====

    def status(self, status:str):
        if not self._status_LED_r:
            return

        if status == 'Z':
            self._status_LED_r.set_fade_dest(1, 20)
            self._status_LED_g.set_fade_dest(0, 0)

        if status == 'A':
            self._status_LED_r.set_fade_dest(0, 0)
            self._status_LED_g.set_fade_dest(10, 20)

        if status == 'WB':
            self._status_LED_r.set_fade_dest(8, 16)
            self._status_LED_g.set_fade_dest(12, 20)

        if status == 'C':
            self._status_LED_r.add_fade_value(3)

        if status == 'P':
            self._status_LED_r.add_fade_value(2)
            self._status_LED_g.add_fade_value(-2)

        if status == 'PE':
            self._status_LED_r.set_fade_value(0)
            self._status_LED_g.set_fade_value(15)

        if status == 'INIT':
            self._status_LED_r.set_fade_dest(1, 25)
            self._status_LED_g.set_fade_dest(0, 25)

#######

