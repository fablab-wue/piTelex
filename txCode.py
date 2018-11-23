#!/usr/bin/python
"""
Telex Code Conversion
Baudot-Code = CCITT-1
Baudot-Murray-Code = CCITT-2

CCITT-2:
543.21      LTRS    FIGS
======      ==========================
000.00	    undef	
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
110.11	    FIGS    FIGS -> #
111.00	    M   	.
111.01	    X   	/
111.10	    V   	=
111.11	    LTRS    LTRS -> $

http://rabbit.eng.miami.edu/info/baudot.html   <<< wrong figs order!
http://www.baudot.net/docs/smith--teletype-codes.pdf
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

#######

class BaudotMurrayCode:
    # Baudot-Murray-Code to ASCII table
    _baLUT = ["~E\nA SIU\rDRJNFCKTZLWHYPQOBG#MXV$", "~3\n- '87\r@4%,~:(5+)2~6019?~#./=$"]
    # Baudot-Murray-Code mode switch codes
    _bSwLUT = [0x1F, 0x1B]

    # Baudot-Murray-Code valic ASCII table
    _valid_char = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-+/=().,:?\'~%@*$#\r\n'
    _replace_char = {
        '&': '(AND)',
        '€': '(EUR)',
        'Ä': 'AE',
        'Ö': 'OE',
        'Ü': 'UE',
        'ß': 'SS',
        '_': '...',
        ';': ',',
        '<': '-(',
        '>': ')-',
        '[': '((',
        ']': '))',
        '{': '(((',
        '}': ')))',
        '"': "'",
        '\t': '(TAB)',
        '\x1B': '(ESC)',
        '\x08': '(BACK)',
        }

    def __init__(self, loopback_mode:bool=True):
        self._ModeA2B = None   # 0=LTRS 1=FIGS
        self._ModeB2A = 0   # 0=LTRS 1=FIGS
        self._loopback_mode = loopback_mode
        

    @staticmethod
    def translate(ansi:str) -> str:
        ret = ''
        ansi = ansi.upper()

        for a in ansi:
            if a not in BaudotMurrayCode._valid_char:
                a = BaudotMurrayCode._replace_char.get(a, '?')
            ret += a
        
        return ret


    def encodeA2B(self, ansi:str) -> list:
        ''' convert an ASCII string to a list of baudot-murray-coded bytes '''
        ret = []

        ansi = ansi.upper()

        if self._ModeA2B == None:
            self._ModeA2B = 0   # letters
            ret.append(self._bSwLUT[self._ModeA2B])

        for a in ansi:
            try: # symbol in current layer?
                b = self._baLUT[self._ModeA2B].index(a)
                if b in self._bSwLUT:
                    self._ModeA2B = self._bSwLUT.index(b)
                ret.append(b)
            except:
                try: # symbol in other layer?
                    b = self._baLUT[1-self._ModeA2B].index(a)
                    self._ModeA2B = 1 - self._ModeA2B
                    ret.append(self._bSwLUT[self._ModeA2B])
                    ret.append(b)
                except: # symbol not found -> ignore
                    pass

        return ret


    def decodeB2A(self, murray:list) -> str:
        ''' convert a list/bytearray of baudot-murray-coded bytes to an ASCII string '''
        ret = ''

        for b in murray:
            try:
                if b in self._bSwLUT:
                    self._ModeB2A = self._bSwLUT.index(b)
                else:
                    a = self._baLUT[self._ModeB2A][b]
                    ret += a
            except:
                pass

        if self._loopback_mode:
            self._ModeA2B = self._ModeB2A # on sending a sysmbol the machine switches itself to other symbol layer

        return ret

#######