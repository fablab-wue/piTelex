#!/usr/bin/python3
"""
Telex Code Conversion
Baudot-Code = CCITT-1
Baudot-Murray-Code = CCITT-2

CCITT-2:
543.21      LTRS    FIGS
======      ==========================
000.00	    undef	undef -> ~
000.01	    E   	3
000.10	    <LF>    <LF>
000.11	    A   	-
001.00	    <SPACE> <SPACE>
001.01	    S   	'
001.10	    I   	8
001.11	    U   	7
010.00	    <CR>    <CR>
010.01	    D   	WRU? -> @
010.10	    R   	4
010.11	    J   	BELL <BEL> -> %
011.00	    N   	,
011.01	    F   	undef, $, Ä, %
011.10	    C   	:
011.11	    K   	(
100.00	    T   	5
100.01	    Z   	+
100.10	    L   	)
100.11	    W   	2
101.00	    H   	undef, #, Ü, Pound
101.01	    Y   	6
101.10	    P   	0
101.11	    Q   	1
110.00	    O   	9
110.01	    B   	?
110.10	    G   	undef, &, Ö, @
110.11	    FIGS    FIGS -> ]
111.00	    M   	.
111.01	    X   	/
111.10	    V   	=
111.11	    LTRS    LTRS -> [

http://rabbit.eng.miami.edu/info/baudot.html   <<< wrong figs order!
http://www.baudot.net/docs/smith--teletype-codes.pdf
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import time

#######

class BaudotMurrayCode:
    # Baudot-Murray-Code to ASCII table
    _LUT_BM2A_STD = ["~E\nA SIU\rDRJNFCKTZLWHYPQOBG]MXV[", "~3\n- '87\r@4%,~:(5+)2~6019?~]./=["]
    _LUT_BM2A_US  = ["~E\nA SIU\rDRJNFCKTZLWHYPQOBG]MXV[", "~3\n- %87\r$4',!:(5\")2@6019?&]./;["]
    # Baudot-Murray-Code mode switch codes
    _LUT_BMsw = [0x1F, 0x1B]

    # Baudot-Murray-Code valid ASCII table
    _valid_char = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-+/=().,:?\'~%$"!&;@#_*<|>[]{}\r\n'
    _replace_char = {
        '&': '(AND)',
        '€': '(EUR)',
        '$': '(USD)',
        '#': '(HASH)',
        '!': '(./)',
        'Ä': 'AE',
        'Ö': 'OE',
        'Ü': 'UE',
        'ß': 'SS',
        ';': '.,',
        '"': "'",
        '\t': '(TAB)',
        '\x1B': '(ESC)',
        '\x08': '(BACK)',
        }

    @staticmethod
    def translate(ansi:str) -> str:
        ret = ''
        ansi = ansi.upper()

        for a in ansi:
            if a not in BaudotMurrayCode._valid_char:
                a = BaudotMurrayCode._replace_char.get(a, '?')
            ret += a
        
        return ret


    @staticmethod
    def do_flip_bits(val:int) -> int:
        ret = 0

        if val & 1:
            ret |= 16
        if val & 2:
            ret |= 8
        if val & 4:
            ret |= 4
        if val & 8:
            ret |= 2
        if val & 16:
            ret |= 1

        return ret


    def __init__(self, loop_back:bool=False, us_coding=False, flip_bits=False, character_duration=0.15, sync_layer:bool=True):
        self._ModeA2BM = None   # 0=LTRS 1=FIGS
        self._ModeBM2A = 0   # 0=LTRS 1=FIGS
        self._flip_bits = flip_bits
        self._loop_back = loop_back
        self._sync_layer = sync_layer
        self._loop_back_eat_bytes = 0
        self._loop_back_expire_time = 0
        self._character_duration = character_duration
        if us_coding:
            self._LUT_BM2A = self._LUT_BM2A_US
        else:
            self._LUT_BM2A = self._LUT_BM2A_STD


    def reset(self):
        self._ModeA2BM = None   # 0=LTRS 1=FIGS


    def encodeA2BM(self, ascii:str) -> list:
        ''' convert an ASCII string to a list of baudot-murray-coded bytes '''
        ret = []

        ascii = ascii.upper()

        if self._ModeA2BM == None:
            self._ModeA2BM = 0   # letters
            ret.append(self._LUT_BMsw[self._ModeA2BM])

        for a in ascii:
            try: # symbol in current layer?
                b = self._LUT_BM2A[self._ModeA2BM].index(a)
                if b in self._LUT_BMsw:   # explicit Bu or Zi
                    self._ModeA2BM = self._LUT_BMsw.index(b)
                ret.append(b)
            except:
                try: # symbol in other layer?
                    b = self._LUT_BM2A[1-self._ModeA2BM].index(a)
                    self._ModeA2BM = 1 - self._ModeA2BM
                    ret.append(self._LUT_BMsw[self._ModeA2BM])
                    ret.append(b)
                except: # symbol not found -> ignore
                    pass

        if self._sync_layer:
            self._ModeBM2A = self._ModeA2BM

        if ret and self._flip_bits:
            for i, b in enumerate(ret):
                ret[i] = self.do_flip_bits(b)

        if self._loop_back:
            l = len(ret)
            self._loop_back_eat_bytes += l
            time_act = time.time()
            if self._loop_back_expire_time < time_act:
                self._loop_back_expire_time = time_act
            self._loop_back_expire_time += l * self._character_duration

        return ret


    def decodeBM2A(self, code:list) -> str:
        ''' convert a list/bytearray of baudot-murray-coded bytes to an ASCII string '''
        ret = ''

        for b in code:
            if self._loop_back and self._loop_back_eat_bytes:
                if time.time()-self._loop_back_expire_time > 6:   # about 40 characters
                    self._loop_back_eat_bytes = 0
                else:
                    self._loop_back_eat_bytes -= 1
                    #if b == 2:
                    #    print(self._loop_back_eat_bytes, time.time()-self._loop_back_expire_time)   # debug
                    continue

            if self._flip_bits:
                b = self.do_flip_bits(b)

            try:
                if b in self._LUT_BMsw:
                    mode = self._LUT_BMsw.index(b)
                    if self._ModeBM2A != mode:
                        self._ModeBM2A = mode
                        if self._loop_back or self._sync_layer:
                            self._ModeA2BM = self._ModeBM2A # on sending a sysmbol the machine switches itself to other symbol layer
                        continue

                a = self._LUT_BM2A[self._ModeBM2A][b]
                #if a == '\n':
                #    print(self._loop_back_eat_bytes, time.time()-self._loop_back_expire_time)   # debug
                ret += a
            except:
                pass

        return ret

#######