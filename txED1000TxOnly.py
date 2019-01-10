#!/usr/bin/python
"""
Telex ED1000 Communication over Sound Card - Transmit Only
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

#import serial
import txCode
import txBase

#######

class TelexED1000TxOnly(txBase.TelexBase):
    def __init__(self, **params):

        super().__init__()

        self._mc = txCode.BaudotMurrayCode()

        self.id = '"'
        self.params = params

        #portname = params.get('portname', '/dev/ttyUSB0')
        #baudrate = params.get('baudrate', 50)
        #bytesize = params.get('bytesize', 5)
        #stopbits = params.get('stopbits', serial.STOPBITS_ONE_POINT_FIVE)
        #loopback = params.get('loopback', True)


    def __del__(self):
        #print('__del__ in TelexSerial')
        super().__del__()
    
    # =====

    def read(self) -> str:
        return ''


    def write(self, a:str, source:str):
        if len(a) != 1:
            return
            
        bb = self._mc.encodeA2B(a)

        #n = self._tty.write(bb)
        #print('-', n, '-')

#######

