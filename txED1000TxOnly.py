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

import time
from threading import Thread

#######

class TelexED1000TxOnly(txBase.TelexBase):
    def __init__(self, **params):

        super().__init__()

        self._mc = txCode.BaudotMurrayCode()

        self.id = '"'
        self.params = params

        baudrate = params.get('baudrate', 50)
        f0 = params.get('f0', 500)
        f1 = params.get('f1', 700)

        self._tx_buffer = []

        self._tx_thread = Thread(target=self.thread_tx)
        self.run = True
        self._tx_thread.start()
        pass

    def __del__(self):
        self.run = False
        #print('__del__ in TelexSerial')
        super().__del__()
    
    # =====

    def read(self) -> str:
        return ''


    def write(self, a:str, source:str):
        if len(a) != 1:
            return
            
        bb = self._mc.encodeA2B(a)

        if bb:
            for b in bb:
                self._tx_buffer.append(b)

        #n = self._tty.write(bb)
        #print('-', n, '-')

    # =====

    def thread_tx(self):
        """Handler for sending tones."""

        while self.run:
            if self._tx_buffer:
                b = self._tx_buffer.pop(0)
                d1 = 1 if b & 1 else 0
                d2 = 1 if b & 2 else 0
                d3 = 1 if b & 4 else 0
                d4 = 1 if b & 8 else 0
                d5 = 1 if b & 16 else 0
                print (b, d1, d2, d3, d4, d5)

            else:   # nothing to send
                pass
        
            time.sleep(0.5)

#######

