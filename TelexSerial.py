#!/usr/bin/python
"""
Telex Serial Communication over CH340-Chip
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import serial
import TelexCode

#######

class TelexSerial:
    def __init__(self, tty_name:str):
        self._mc = TelexCode.BaudotMurrayCode()

        # init serial
        self._tty = serial.Serial(tty_name)
        self._tty.rts = True    # RTS -> Low
        self._tty.dtr = True    # DTR -> Low

        if 50 not in self._tty.BAUDRATES:
            raise Exception('Baudrate not supported')
        if 5 not in self._tty.BYTESIZES:
            raise Exception('Databits not supported')
        if 1.5 not in self._tty.STOPBITS:
            raise Exception('Stopbits not supported')

        self._tty.baudrate = 50
        self._tty.bytesize = 5
        self._tty.stopbits = serial.STOPBITS_ONE_POINT_FIVE

        self._is_transmitting = False
        self._rx_buffer = ''


    def __del__(self):
        #print('__del__ in TelexSerial')
        self._tty.close()
    

    def read(self) -> str:
        if self._is_transmitting and not self._tty.out_waiting:
            self._is_transmitting = False
            self._tty.rts = True   # RTS -> Low

        ret = ''

        if self._rx_buffer:
            ret += self._rx_buffer
            self._rx_buffer = ''

        if self._tty.in_waiting:
            m = self._tty.read(1)
            ret += self._mc.decode(m)

        return ret


    def write(self, a:str):
        if a.find('#') >= 0:   # found 'Wer da?'
            a = a.replace('#', '')
            self._rx_buffer += '<ID>'

        m = self._mc.encode(a)

        self._is_transmitting = True
        self._tty.rts = False   # RTS -> High -> no loopback

        self._tty.write(m)

#######

