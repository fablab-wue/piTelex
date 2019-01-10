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
import txCode
import txBase

#######

class TelexSerial(txBase.TelexBase):
    def __init__(self, **params):

        super().__init__()

        self._mc = txCode.BaudotMurrayCode()

        self.id = '~'
        self.params = params

        portname = params.get('portname', '/dev/ttyUSB0')
        baudrate = params.get('baudrate', 50)
        bytesize = params.get('bytesize', 5)
        stopbits = params.get('stopbits', serial.STOPBITS_ONE_POINT_FIVE)
        loopback = params.get('loopback', True)

        # init serial
        self._tty = serial.Serial(portname, write_timeout=0)
        self._tty.rts = True    # RTS -> Low
        self._tty.dtr = True    # DTR -> Low

        if baudrate not in self._tty.BAUDRATES:
            raise Exception('Baudrate not supported')
        if bytesize not in self._tty.BYTESIZES:
            raise Exception('Databits not supported')
        if stopbits not in self._tty.STOPBITS:
            raise Exception('Stopbits not supported')

        self._tty.baudrate = baudrate
        self._tty.bytesize = bytesize
        self._tty.stopbits = stopbits

        self._loopback = loopback
        self._rx_buffer = []
        self._tx_eat_bytes = 0
        self._counter_LTRS = 0
        self._counter_FIGS = 0


    def __del__(self):
        #print('__del__ in TelexSerial')
        self._tty.close()
        super().__del__()
    
    # =====

    def read(self) -> str:
        ret = ''

        if self._tty.in_waiting:
            b = self._tty.read(1)
            a = self._mc.decodeB2A(b)
            if self._tx_eat_bytes:
                self._tx_eat_bytes -= 1
                return ''
            
            if a:
                self._rx_buffer.append(a)

            if b == 0x1F:
                self._counter_LTRS += 1
                if self._counter_LTRS == 5:
                    self._rx_buffer.append('\x1b$')
            else:
                self._counter_LTRS = 0

            if b == 0x1B:
                self._counter_FIGS += 1
                if self._counter_FIGS == 5:
                    self._rx_buffer.append('\x1b#')
            else:
                self._counter_FIGS = 0

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            return
            
        if a == '#':
            a = '@'   # ask teletype for hardware ID

        bb = self._mc.encodeA2B(a)

        n = self._tty.write(bb)
        if not self._loopback:
            self._tx_eat_bytes += n
        #print('-', n, '-')

#######

