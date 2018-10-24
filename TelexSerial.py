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
    def __init__(self, id:str, tty_name:str):
        self._mc = TelexCode.BaudotMurrayCode()

        self._id = id

        # init serial
        self._tty = serial.Serial(tty_name, write_timeout=0)
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

        self._rx_buffer = ''
        self._tx_eat_bytes = 0
        self._counter_LTRS = 0
        self._counter_FIGS = 0


    def __del__(self):
        #print('__del__ in TelexSerial')
        self._tty.close()
    

    def read(self) -> str:
        ret = ''

        if self._tty.in_waiting:
            m = self._tty.read(1)
            ret += self._mc.decode(m)

            if self._tx_eat_bytes:
                self._tx_eat_bytes -= 1
                return ''

            if m == 0x1F:
                self._counter_LTRS += 1
                if self._counter_LTRS == 5:
                    ret += '\x02'
            else:
                self._counter_LTRS = 0

            if m == 0x1B:
                self._counter_FIGS += 1
                if self._counter_FIGS == 5:
                    ret += '\x01'
            else:
                self._counter_FIGS = 0

        if self._rx_buffer:
            ret += self._rx_buffer
            self._rx_buffer = ''

        return ret


    def write(self, a:str, loopback:bool=True):
        if self._id and a.find('@') >= 0:   # found 'Wer da?'
            a = a.replace('@', '')
            self._rx_buffer += self._id

        m = self._mc.encode(a)

        n = self._tty.write(m)
        if not loopback:
            self._tx_eat_bytes += n
        #print('-', n, '-')

#######

