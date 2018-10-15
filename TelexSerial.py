#!/usr/bin/python
"""
testTelex for RPi Zero W
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import serial
import MurrayCode

#######

class TelexSerial:
    def __init__(self, tty_name:str):
        self._mc = MurrayCode.MurrayCode()
        self._tty = serial.Serial(tty_name)
        self._tty = serial.rs485.RS485Settings(True, False, False, None, None)   # set RTS to 1 when transmitting

        if 50 not in self._tty.BAUDRATES:
            raise Exception('Baudrate not supported')
        if 5 not in self._tty.BYTESIZES:
            raise Exception('Databits not supported')
        if 1.5 not in self._tty.STOPBITS:
            raise Exception('Stopbits not supported')

        self._tty.baudrate = 50
        self._tty.bytesize = 5
        #self._tty.stopbits = serial.STOPBITS_TWO
        self._tty.stopbits = serial.STOPBITS_ONE_POINT_FIVE


    def __exit__(self,exc_type, exc_val, exc_tb):
        self._tty.close()
    
    def read(self) -> str:
        if not self._tty.in_waiting:
            return ''
        m = self._tty.read(1)
        a = self._mc.decode(m)
        return a

    def write(self, a:str):
        m = self._mc.encode(a)
        #return self._tty.write(m)
        pass

#######

