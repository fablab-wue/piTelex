#!/usr/bin/python
"""
Telex Serial Communication over CH340-Chip (not FTDI or Prolific)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import time

import txBase

#######

class TelexLog(txBase.TelexBase):
    def __init__(self, mode:str, **params):

        super().__init__()

        self.id = '"'
        self.params = params

        self._filename = params.get('filename', 'log.txt')

        self._last_time = self._last_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self._last_source = ' '
        self._line = '================================================================================'


    def __del__(self):
        super().__del__()
    
    # =====

    def read(self) -> str:
        return ''


    def write(self, a:str, source:str):
        out = False
        add = ''

        if a == '\r':
            a = '<'
        if a == '\n':
            a = '|'
        if len(a) > 1:
            a = '{' + a[1:] + '}'

        if source == self._last_source and a == '|':
            out = True
            add = '|'
            a = ''

        elif source == self._last_source and len(self._line) >= 80:
            out = True
            add = ' \\'

        if source != self._last_source:
            out = True
        
        if out:
            line = self._last_time
            line += '  '
            line += self._last_source
            line += ':  '
            line += self._line
            line += add

            #print()
            #print(line)
            
            with open(self._filename, 'a') as fp:
                line += '\n'
                fp.write(line)

            self._line = ''
            self._last_time = ''
            self._last_source = source

        self._line += a

        if not self._last_time:
            self._last_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


#######

