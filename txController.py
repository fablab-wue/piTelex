#!/usr/bin/python
"""
Telex Serial Communication over CH340-Chip
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txBase

#######

class TelexController(txBase.TelexBase):
    def __init__(self, device_id:str):
        self.device_id = device_id

        self.id = '§'
        self._rx_buffer = []

    def __del__(self):
        pass
    

    def read(self) -> str:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if self.device_id and a == '@':   # found 'Wer da?'
            self._rx_buffer.extend(list(self.device_id))   # send back device id
            return True

        if a == '\x1b#':   # set to dial mode
            return True

        if a == '\x1b$':   # set to connect mode
            return True

#######

