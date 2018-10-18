#!/usr/bin/python
"""
Telex Code Conversion
Baudot-Code = CCITT-1
Baudot-Murray-Code = CCITT-2
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

#######

'''
http://rabbit.eng.miami.edu/info/baudot.html
 MurrayLTRS.index('A') -> 3
 MurrayLTRS[3] -> 'A'
'''

class BaudotMurrayCode:
    _MurrayLUT = ['\x80E\nA SIU\rDRJNFCKTZLWHYPQOBG\x82MXV\x81', '\x803\n- \'87\r#4\a,\x80:(5+)2\x806019?\x80\x82./=\x81']
    _MurraySwitchLUT = [0x1F, 0x1B]

    def __init__(self):
        self._ModeA2M = None
        self._ModeM2A = 0   # letters
        
    def encode(self, ansi:str) -> list:
        ''' convert an ansi string to a list of baudot-murray-coded bytes '''
        ret = []

        ansi = ansi.upper()

        if self._ModeA2M == None:
            self._ModeA2M = 0   # letters
            ret.append(self._MurraySwitchLUT[self._ModeA2M])

        for a in ansi:
            try:
                m = self._MurrayLUT[self._ModeA2M].index(a)
                ret.append(m)
            except:
                try:
                    m = self._MurrayLUT[1-self._ModeA2M].index(a)
                    self._ModeA2M = 1 - self._ModeA2M
                    ret.append(self._MurraySwitchLUT[self._ModeA2M])
                    ret.append(m)
                except:
                    pass

        return ret


    def decode(self, murray:list) -> str:
        ''' convert a list/bytearray of baudot-murray-coded bytes to an ansi string '''
        ret = ''

        for m in murray:
            try:
                a = self._MurrayLUT[self._ModeM2A][m]
                if ord(a) >= 0x80:
                    if ord(a) == 0x81:
                        self._ModeM2A = 0   # letters
                    if ord(a) == 0x82:
                        self._ModeM2A = 1   # numbers
                else:
                    ret += a
            except:
                pass

        return ret

#######
