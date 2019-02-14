#!/usr/bin/python
"""
Telex Device - Serial Communication over Rasperry Pi (Zero W)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

#https://www.programcreek.com/python/example/93338/pigpio.pi

import time
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html   pip install pigpio

import txCode
import txBase

pi = pigpio.pi()

#######

class TelexRPiTTY(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self._tx_buffer = []
        self._rx_buffer = []
        self._cb = None
        self._is_pulse_dial = False
        self._pulse_dial_count = 0

        self.id = '#'
        self.params = params

        self._baudrate = params.get('baudrate', 50)
        self._bytesize = params.get('bytesize', 5)
        self._stopbits = params.get('stopbits', 1.5)
        self._pin_txd = params.get('pin_txd', 17)
        self._pin_rxd = params.get('pin_rxd', 27)
        self._pin_rel = params.get('pin_rel', 22)
        self._pin_dir = params.get('pin_dir', 11)
        #self._pin_oin = params.get('pin_oin', 10)
        self._pin_opt = params.get('pin_opt', 9)
        #self._pin_sta = params.get('pin_sta', 12)
        self._inv_rxd = params.get('inv_rxd', False)
        #self._inv_txd = params.get('inv_txd', False)
        self._loopback = params.get('loopback', True)
        self._uscoding = params.get('uscoding', True)

        # init codec
        character_duration = (self._bytesize + 1.0 + self._stopbits) / self._baudrate
        self._mc = txCode.BaudotMurrayCode(self._loopback, us_coding=self._uscoding, character_duration=character_duration)
        
        # init GPIOs
        pi.set_pad_strength(0, 8)

        pi.set_mode(self._pin_rxd, pigpio.INPUT)
        pi.set_pull_up_down(self._pin_rxd, pigpio.PUD_UP)
        
        pi.set_mode(self._pin_txd, pigpio.OUTPUT)
        #pi.write(self._pin_txd, not self._inv_txd)
        pi.write(self._pin_txd, 1)
        pi.set_mode(self._pin_opt, pigpio.OUTPUT)
        pi.write(self._pin_opt, 0)
        pi.set_mode(self._pin_rel, pigpio.OUTPUT)   # relais for commutating
        pi.write(self._pin_rel, 0)   # pos polarity
        pi.set_mode(self._pin_dir, pigpio.OUTPUT)   # direction of comminication
        pi.write(self._pin_dir, 0)   # 1=transmitting

        # init bit bongo serial read
        pi.set_glitch_filter(self._pin_rxd, 1000)   # 1ms
        status = pi.bb_serial_read_open(self._pin_rxd, self._baudrate, self._bytesize)   # 50 baud
        pi.bb_serial_invert(self._pin_rxd, self._inv_rxd)

        # init bit bongo serial write
        self.last_wid = None

        # debug
        cbs = pi.wave_get_max_cbs()
        micros = pi.wave_get_max_micros()
        pulses = pi.wave_get_max_pulses()
        pass


    def __del__(self):
        status = pi.bb_serial_read_close(self._pin_rxd)
        pi.wave_clear()
        super().__del__()
    
    # =====

    def read(self) -> str:
        #if not self._tty.in_waiting:
        ret = ''

        count, data = pi.bb_serial_read(self._pin_rxd)
        if count:
            bb = data
            a = self._mc.decodeBM2A(bb)
            if a:
                self._rx_buffer.append(a)
        
        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            return

        bb = self._mc.encodeA2BM(a)
    
        if bb:
            for b in bb:
                self._tx_buffer.append(b)
            self._write_wave()


    def idle(self):
        if self._tx_buffer:
            self._write_wave()


    # =====

    def _write_wave(self):
        if not self._tx_buffer:
            return

        if pi.wave_tx_busy():   # last wave is still transmitting
            return

        #pi.wave_clear()

        pi.wave_add_generic([pigpio.pulse(1<<self._pin_dir, 0, 10)]) # add dir pulse to waveform

        pi.wave_add_serial(self._pin_txd, self._baudrate, self._tx_buffer, 0, self._bytesize, 3)

        pi.wave_add_generic([pigpio.pulse(0, 1<<self._pin_dir, 10)]) # add dir pulse to waveform

        new_wid = pi.wave_create() # commit waveform
        pi.wave_send_once(new_wid) # transmit waveform

        if self.last_wid is not None:
            pi.wave_delete(self.last_wid) # delete no longer used waveform

        print("wid", self.last_wid, "new_wid", new_wid) # debug

        self.last_wid = new_wid

        self._tx_buffer = []


    def enable_pulse_dial(self, enable:bool):
        if self._cb:
            self._cb.cancel()
            self._cb = None

        if enable:
            self._cb = pi.callback(self._pin_rxd, pigpio.FALLING_EDGE, self._callback_pulse_dial)
            pi.set_watchdog(self._pin_rxd, 150)   # 150ms
        else:
            pi.set_watchdog(self._pin_rxd, 0)   # disable


    def _callback_pulse_dial(self, gpio, level, tick):
        print(gpio, level, tick)

        if level == pigpio.TIMEOUT:   # watchdog timeout
            if self._pulse_dial_count == 10:
                self._pulse_dial_count = 0
            self._rx_buffer += str(self._pulse_dial_count)
            self._pulse_dial_count = 0
        else:
            self._pulse_dial_count += 1

#######

