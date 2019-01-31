#!/usr/bin/python
"""
Telex Serial Communication over CH340-Chip (not FTDI or Prolific)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import serial
import time

import txCode
import txBase

#######

class TelexSerial(txBase.TelexBase):
    def __init__(self, **params):

        super().__init__()

        self.id = '~'
        self.params = params

        portname = params.get('portname', '/dev/ttyUSB0')
        self._baudrate = params.get('baudrate', 50)
        bytesize = params.get('bytesize', 5)
        stopbits = params.get('stopbits', serial.STOPBITS_ONE_POINT_FIVE)
        loopback = params.get('loopback', True)
        uscoding = params.get('uscoding', False)

        self._mc = txCode.BaudotMurrayCode(loopback, uscoding)

        # init serial
        self._tty = serial.Serial(portname, write_timeout=0)
        self._tty.dtr = False   # DTR -> High
        self._tty.rts = False   # RTS -> High

        if self._baudrate not in self._tty.BAUDRATES:
            raise Exception('Baudrate not supported')
        if bytesize not in self._tty.BYTESIZES:
            raise Exception('Databits not supported')
        if stopbits not in self._tty.STOPBITS:
            raise Exception('Stopbits not supported')

        self._tty.baudrate = self._baudrate
        self._tty.bytesize = bytesize
        self._tty.stopbits = stopbits

        self._loopback = loopback
        self._rx_buffer = []
        self._counter_LTRS = 0
        self._counter_FIGS = 0
        self._counter_dial = 0
        self._time_last_dial = 0
        self._TW_mode = 39
        self._is_FS_enable = (self._TW_mode == 0)
        self._cts_stable = False   # High 
        self._cts_counter = 0
        self._ignore_til_time = time.time() + 0.5


    def __del__(self):
        #print('__del__ in TelexSerial')
        self._tty.close()
        super().__del__()
    
    # =====

    def read(self) -> str:
        if self._tty.in_waiting:
            a = ''

            bb = self._tty.read(1)
            if time.time() < self._ignore_til_time:
                return

            if self._is_FS_enable:
                a = self._mc.decodeBM2A(bb)

                self._check_special_sequences(a)

            else:
                b = bb[0]

                if b == 0:   # break or idle mode
                    #self._rx_buffer.append('\x1bST')
                    pass
                elif (b & 0x13) == 0x10:   # valid dial pulse
                    self._counter_dial += 1
                    self._time_last_dial = time.time()
            
            if a:
                self._rx_buffer.append(a)
            
            self._cts_counter = 0

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)
            return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            self._check_commands(a)
            return
            
        if a == '#':
            a = '@'   # ask teletype for hardware ID

        bb = self._mc.encodeA2BM(a)

        self._tty.write(bb)


    def idle20Hz(self):
        if 1:
            time_act = time.time()

            if self._counter_dial and (time_act - self._time_last_dial) > 0.5:
                if self._counter_dial >= 10:
                    self._counter_dial = 0
                a = str(self._counter_dial)
                self._rx_buffer.append(a)
                self._time_last_dial = time_act
                self._counter_dial = 0

            cts = self._tty.cts
            if cts != self._cts_stable:
                self._cts_counter += 1
                if self._cts_counter == 20:
                    self._cts_stable = cts
                    print(cts)
                    if cts:   # Low
                        self._rx_buffer.append('\x1bST')
                        pass
                    elif not self._is_FS_enable:   # High
                        self._rx_buffer.append('\x1bAT')
                        pass
                    pass
            else:
                self._cts_counter = 0


    def _enable_FS(self, enable:bool):
        self._tty.dtr = enable    # DTR -> True=Low=motor_on
        self._tty.rts = enable    # RTS
        self._is_FS_enable = enable
        self._mc.reset()
        self._set_ignore_time(0.5)


    def _enable_pulse_dial(self, enable:bool):
        if enable:
            self._tty.baudrate = 75
        else:
            self._tty.baudrate = self._baudrate


    def _check_special_sequences(self, a:str):
        if self._TW_mode == 0:
            if a == '[':
                self._counter_LTRS += 1
                if self._counter_LTRS == 5:
                    self._rx_buffer.append('\x1bST')
            else:
                self._counter_LTRS = 0

            if a == ']':
                self._counter_FIGS += 1
                if self._counter_FIGS == 5:
                    self._rx_buffer.append('\x1bAT')
            else:
                self._counter_FIGS = 0


    def _check_commands(self, a:str):
        enable = None

        if a == '\x1bA':
            self._enable_pulse_dial(False)
            enable = True

        if a == '\x1bZ':
            self._enable_pulse_dial(False)
            enable = (self._TW_mode == 0)
            self._set_ignore_time(1.5)

        if a == '\x1bWB':
            if self._TW_mode == 39:   # TW39
                self._enable_pulse_dial(True)
                self._tty.write(b'\x01')   # send pulse with 25ms low to signal 'ready for dialing' ('Wahlbereitschaft')
                enable = False
            else:   # dedicated line, TWM
                enable = True

        if enable is not None:
            self._enable_FS(enable)


    def _set_ignore_time(self, t_diff):
        t = time.time() + t_diff
        if self._ignore_til_time < t:
            self._ignore_til_time = t

#######

