#!/usr/bin/python3
"""
Telex Serial Communication over CH340-Chip
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txCode

#######

class TelexBase:
    def __init__(self):
        self.id = '?'
        self.loopback = True


    def __del__(self):
        #print('__del__ in TelexSerial')
        pass
    

    def read(self) -> str:
        return ''


    def write(self, a:str, source:str):
        pass

    def idle(self):
        pass

    def idle20Hz(self):
        pass

    def exit(self):
        pass

#######

