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

#REMOTE_IP = None
REMOTE_IP = '10.23.42.234'

pi = pigpio.pi(REMOTE_IP)

#######

class TelexRPiTTY(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

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

        self.id = '#'
        self.params = params

        self._baudrate = params.get('baudrate', 50)
        self._bytesize = params.get('bytesize', 5)
        self._stopbits = params.get('stopbits', 1.5)
        self._stopbits2 = int(self._stopbits * 2 + 0.5)
        self._pin_txd = params.get('pin_txd', 17)
        self._pin_rxd = params.get('pin_rxd', 27)
        self._pin_fsg_ns = params.get('pin_fsg_ns', 27)
        self._pin_rel = params.get('pin_rel', 22)
        self._pin_dir = params.get('pin_dir', 11)
        #self._pin_oin = params.get('pin_oin', 10)
        self._pin_opt = params.get('pin_opt', 9)
        #self._pin_sta = params.get('pin_sta', 12)
        self._inv_rxd = params.get('inv_rxd', False)
        #self._inv_txd = params.get('inv_txd', False)
        self._loopback = params.get('loopback', True)
        self._uscoding = params.get('uscoding', False)

        # init codec
        character_duration = (self._bytesize + 1.0 + self._stopbits) / self._baudrate
        self._mc = txCode.BaudotMurrayCode(self._loopback, us_coding=self._uscoding, character_duration=character_duration)
        
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
        pi.set_mode(self._pin_rel, pigpio.OUTPUT)   # relais for commutating
        pi.write(self._pin_rel, 0)   # pos polarity
        pi.set_mode(self._pin_dir, pigpio.OUTPUT)   # direction of comminication
        pi.write(self._pin_dir, 0)   # 1=transmitting

        # init bit bongo serial read
        try:
            status = pi.bb_serial_read_close(self._pin_rxd)
        except:
            pass
        status = pi.bb_serial_read_open(self._pin_rxd, self._baudrate, self._bytesize)
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
        if count \
            and (not self._use_squelch or time.time() >= self._time_squelch) \
            and not self._is_pulse_dial:
            bb = data
            a = self._mc.decodeBM2A(bb)
            if a:
                self._rx_buffer.append(a)
            
            self._rxd_counter = 0
        
        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            self._check_commands(a)
            return

        if a == '#':
            a = '@'   # ask teletype for hardware ID

        if a:
            self._tx_buffer.append(a)
            self._write_wave()

    # =====

    def idle20Hz(self):
        #time_act = time.time()

        if self._use_rxd_observation:
            rxd = pi.read(self._pin_rxd)   #debug
            rxd = (not pi.read(self._pin_rxd)) == self._inv_rxd   # logical xor
            if rxd != self._rxd_stable:
                self._rxd_counter += 1
                if self._rxd_counter == 10:   # 0.5sec
                    self._rxd_stable = rxd
                    print(rxd)   # debug
                    if not rxd:   # rxd=Low
                        self._rx_buffer.append('\x1bST')
                        pass
                    elif not self._is_enabled:   # rxd=High
                        self._rx_buffer.append('\x1bAT')
                        pass
                    pass
            else:
                self._rxd_counter = 0

    # -----

    def idle(self):
        if self._tx_buffer:
            self._write_wave()


    # =====

    def _write_wave(self):
        if (self._use_squelch and time.time() <= self._time_squelch) \
            or not self._tx_buffer \
            or pi.wave_tx_busy():   # last wave is still transmitting
            return

        #a = self._tx_buffer.pop(0)
        a = ''.join(self._tx_buffer)
        self._tx_buffer = []
        bb = self._mc.encodeA2BM(a)
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

        #print("wid", self.last_wid, "new_wid", new_wid) # debug

        self.last_wid = new_wid

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
                self._cb = pi.callback(self._pin_fsg_ns, pigpio.RISING_EDGE, self._callback_pulse_dial)
                pi.set_watchdog(self._pin_fsg_ns, 2500)   # 250ms
            else:
                pi.set_watchdog(self._pin_fsg_ns, 0)   # disable

    # -----

    def _callback_pulse_dial(self, gpio, level, tick):

        if level == pigpio.TIMEOUT:   # watchdog timeout
            print(gpio, level, tick)   # debug
            if self._pulse_dial_count:
                if self._pulse_dial_count == 10:
                    self._pulse_dial_count = 0
                self._rx_buffer += str(self._pulse_dial_count)
                self._pulse_dial_count = 0
        else:   # pigpio.FALLING_EDGE
            self._pulse_dial_count += 1

    # -----

    def _check_commands(self, a:str):
        enable = None

        if a == '\x1bA':
            self._set_pulse_dial(False)
            self._set_online(True)
            enable = True

        if a == '\x1bZ':
            self._tx_buffer = []    # empty write buffer...
            self._set_pulse_dial(False)
            self._set_online(False)
            enable = False   #self._use_dedicated_line
            if not enable and self._use_squelch:
                self._set_time_squelch(1.5)

        if a == '\x1bWB':
            self._set_online(True)
            if self._use_pulse_dial:   # TW39
                self._set_pulse_dial(True)
                self._tx_buffer.append('[')
                enable = False
            else:   # dedicated line, TWM, V.10
                enable = True

        if enable is not None:
            self._set_enable(enable)

    # -----

    def _set_time_squelch(self, t_diff:float):
        t = time.time() + t_diff
        if self._time_squelch < t:
            self._time_squelch = t

#######

