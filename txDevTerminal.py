#!/usr/bin/python3
"""
Telex Device - Serial Communication over System TTY in ASCII-Mode

"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import serial
import time

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import log

#######

class TelexTerminal(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'Trm'
        self.params = params

        portname = params.get('portname', '/dev/ttyUSB0')
        baudrate = params.get('baudrate', 300)
        bytesize = params.get('bytesize', 8)
        stopbits = params.get('stopbits', serial.STOPBITS_ONE)
        parity   = params.get('parity', serial.PARITY_NONE)
        self._local_echo = params.get('loc_echo', True)

        self._rx_buffer = []

        # init serial
        self._tty = serial.Serial(portname, write_timeout=0)

        if baudrate not in self._tty.BAUDRATES:
            raise Exception('Baudrate not supported')
        if bytesize not in self._tty.BYTESIZES:
            raise Exception('Databits not supported')
        if stopbits not in self._tty.STOPBITS:
            raise Exception('Stopbits not supported')
        if parity not in self._tty.PARITIES:
            raise Exception('Parity not supported')

        self._tty.baudrate = baudrate
        self._tty.bytesize = bytesize
        self._tty.stopbits = stopbits
        self._tty.parity = parity

    # -----

    def exit(self):
        self._tty.close()

    # -----

    def __del__(self):
        super().__del__()

    # =====

    def read(self) -> str:
        if self._tty.in_waiting:
            b = self._tty.read(1)
            if b[0] < 0x20:
                pass
            else:
                if self._local_echo:
                    self._tty.write(b)
                a = b.decode('ASCII', errors='ignore')
                if a:
                    a = a.upper()
                    self._rx_buffer.append(a)

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)
            return ret

    # -----

    def write(self, a:str, source:str):
        if len(a) != 1:
            self._check_commands(a)
            a = '{' + a[1:] + '}'

        if a:
            a = a.lower()
            b = a.encode('ASCII')
            self._tty.write(b)

    # =====

    def idle20Hz(self):
        pass

    # -----

    def idle(self):
        pass

    # =====

    def _check_commands(self, a:str):
        if a == '\x1bA':
            pass

        if a == '\x1bZ':
            pass

        if a == '\x1bWB':
            pass

#######
