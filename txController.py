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
    _fontstr = {'A': 'VSSV', 'B': '[YYR', 'C': 'CZZZ', 'D': '[ZZC', 'E': '[YYZ', 'F': '[SSE', 'G': 'CZYX', 'H': '[  [', 'I': 'Z[Z', 'J': '<TZK', 'K': '[ RZ', 'L': '[TTT', 'M': '[|M|[', 'N': '[| [', 'O': 'CZZZC', 'P': '[SS|', 'Q': 'CZBV', 'R': '[SFL', 'S': 'LYYD', 'T': 'EE[EE', 'U': 'KTTK', 'V': 'U<T<U', 'W': '[<I<[', 'X': 'ZR RZ', 'Y': 'E|M|E', 'Z': 'ZBYWZ', '0': 'CZZC', '1': 'L[T', '2': 'BYYL', '3': 'ZYYR', '4': 'U V ', '5': 'UYYD', '6': 'NPYD', '7': 'EBSA', '8': 'RYYR', '9': 'LYFI', '.': 'OO', ',': 'ON', ';': 'GR', '+': '  [  ', '-': '    ', '*': 'YC CY', '/': 'T< |E', '=': 'RRRR', '(': 'CZ', ')': 'ZC', '?': 'EYY|', "'": 'AA', ' ': '~~', '': '~', '\r': '  RZZ', '<': '  RZZ', '\n': 'YYYYY', '|': 'YYYYY'}
    _fontsep = '~'


    def __init__(self, device_id:str):
        self.device_id = device_id

        self.id = '§'
        self.params = {}
        self._rx_buffer = []

        self._font_mode = False


    def __del__(self):
        pass
    

    def read(self) -> str:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if self.device_id and a == '#':   # found 'Wer da?'
            self._rx_buffer.extend(list(self.device_id))   # send back device id
            return True


        if a == '\x1bAT':   # AT
            self._rx_buffer.extend(list('\x1bA'))   # send text
            return True

        if a == '\x1bST':   # ST
            self._rx_buffer.extend(list('\x1bZ'))   # send text
            return True

        if a == '\x1bLT':   # LT
            self._rx_buffer.extend(list('\x1bA'))   # send text
            return True


        if a == '\x1bFONT':   # set to font mode
            self._font_mode = not self._font_mode
            return True

        if self._font_mode:   # 
            f = self._fontstr.get(a, None)
            if f:
                f += self._fontsep
                self._rx_buffer.extend(list(f))   # send back font pattern
            return True


        if a == '\x1bLOREM':   # print LOREM IPSUM
            self._rx_buffer.extend(list('LOREM IPSUM DOLOR SIT AMET, CONSETETUR SADIPSCING ELITR, SED DIAM'))   # send text
            return True


        if a == '\x1bRY':   # print RY pattern
            self._rx_buffer.extend(list('RYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRY'))   # send text
            return True


        if a == '\x1bABC':   # print ABC pattern
            self._rx_buffer.extend(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890 .,-+=/()?\'%'))   # send text
            return True


#######

