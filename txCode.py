#!python3
"""
Telex Code Conversion
Baudot-Code = CCITT-1
Baudot-Murray-Code = CCITT-2
CCITT-2:
| 543.21 | 12.345 | A | 1 | PA| P1| 
===================================
| 000.00 | 00.000 | ▨ | ▨ | ~ | ~ | 
| 000.01 | 10.000 | E | 3 | Е | 3 | 
| 000.10 | 01.000 | ≡ | ≡ | ≡ | ≡ | ≡=<LF>
| 000.11 | 11.000 | A | - | А | - | 
| 001.00 | 00.100 | ⎵ | ⎵ | ⎵ | ⎵ | ⎵=<SPACE>
| 001.01 | 10.100 | S | ' | С | ' | 
| 001.10 | 01.100 | I | 8 | И | 8 | 
| 001.11 | 11.100 | U | 7 | У | 7 | 
| 010.00 | 00.010 | ❮ | ❮ | ❮ | ❮ | ❮=<CR>
| 010.01 | 10.010 | D | ✠ | Д | ✠ | ✠=WRU? -> @
| 010.10 | 01.010 | R | 4 | Р | 4 | 
| 010.11 | 11.010 | J | ⍾ | Й | Ю | ⍾=BELL <BEL> -> %
| 011.00 | 00.110 | N | , | Н | , | 
| 011.01 | 10.110 | F | ▨ | Ф | Э | 
| 011.10 | 01.110 | C | : | Ц | : | 
| 011.11 | 11.110 | K | ( | К | ( | 
| 100.00 | 00.001 | T | 5 | Т | 5 | 
| 100.01 | 10.001 | Z | + | З | + | 
| 100.10 | 01.001 | L | ) | Л | ) | 
| 100.11 | 11.001 | W | 2 | В | 2 | 
| 101.00 | 00.101 | H | ▨ | Х | Щ | 
| 101.01 | 10.101 | Y | 6 | Ы | 6 | 
| 101.10 | 01.101 | P | 0 | П | 0 | 
| 101.11 | 11.101 | Q | 1 | Я | 1 | 
| 110.00 | 00.011 | O | 9 | О | 9 | 
| 110.01 | 10.011 | B | ? | Б | ? | 
| 110.10 | 01.011 | G | ▨ | Г | Ш | 
| 110.11 | 11.011 | ] | ] | ] | ] | FIGS -> ]
| 111.00 | 00.111 | M | . | М | . | 
| 111.01 | 10.111 | X | / | Ь | / | 
| 111.10 | 01.111 | V | = | Ж | = | 
| 111.11 | 11.111 | [ | [ | [ | [ | LTRS -> [

http://rabbit.eng.miami.edu/info/baudot.html   <<< wrong figs order!
http://www.baudot.net/docs/smith--teletype-codes.pdf
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.2"

import time
import unicodedata
#from unidecode import unidecode

#######

class BaudotMurrayCode:
    # Baudot-Murray-Code to ASCII table
    _LUT_BM2A_ITA2 = (
        "~E\nA SIU\rDRJNFCKTZLWHYPQOBG]MXV[", 
        "~3\n- '87\r@4%,~:(5+)2~6019?~]./=["
    )
    _LUT_BM2A_US = (
        "~E\nA SIU\rDRJNFCKTZLWHYPQOBG]MXV[", 
        "~3\n- %87\r$4',!:(5\")2@6019?&]./;["
    )
    _LUT_BM2A_MKT2 = (
        "~E\nA SIU\rDRJNFCKTZLWHYPQOBG]MXV[", 
        "~3\n- '87\r@4Ю,Э:(5+)2Щ6019?Ш]./=[",
        "~Е\nА СИУ\rДРЙНФЦКТЗЛВХЫПЯОБГ]МЬЖ["
    )
    # Baudot-Murray-Code mode switch codes
    _LUT_BMsw_ITA2 = (0x1F, 0x1B)
    _LUT_BMsw_US = (0x1F, 0x1B)
    _LUT_BMsw_MKT2 = (0x1F, 0x1B, 0x00)

    # Baudot-Murray-Code valid ASCII table
    #_valid_char = " ABCDEFGHIJKLMNOPQRSTUVWXYZ~3\n- '87\r@4%,~:(5+)2~6019?~]./=[#"
    _valid_convert_chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-+=:/()?.,'\n\r"
    _LUT_convert_chars = {
        'Ä': 'AE',
        'Ö': 'OE',
        'Ü': 'UE',
        'ß': 'SS',
        '\a': '%',   # Bell
        '\f': '(FF)',   # Form Feed
        '\d': '(DEL)',   # Delete
        '\t': '(TAB)',   # Tab
        '\v': '(VT)',   # Vertical Tab
        '\x1B': '(ESC)',   # Escape
        '\b': '(BS)',   # Backspace
        '\x08': '(BS)',   # Backspace
        '&': '(AND)',
        '€': '(EUR)',
        '$': '(USD)',
        '<': '(LT)',
        '>': '(GT)',
        '|': '(PIPE)',
        '*': '(STAR)',
        '#': '(HASH)',
        '@': '(AT)',
        '"': "'",
        ';': ',.',
        '!': '(./)',
        '%': '(./.)',
        '[': '(',
        ']': ')',
        '{': '-(',
        '}': ')-',
        '\\': '/',
        '_': '--',
        }

    CODING_ITA2 = 0
    CODING_US = 1
    CODING_MKT2 = 2

    # =====

    @staticmethod
    def translate(text:str) -> str:
        return BaudotMurrayCode.ascii_to_tty_text(text)

    # -----

    @staticmethod
    def ascii_to_tty_text(text:str) -> str:
        ret = ''

        text = text.upper()

        for a in text:
            try:
                if a not in BaudotMurrayCode._valid_convert_chars:
                    if a in BaudotMurrayCode._LUT_convert_chars:
                        a = BaudotMurrayCode._LUT_convert_chars.get(a, '?')
                    else:
                        nkfd_norm = unicodedata.normalize('NFKD', a)
                        a =  u"".join([c for c in nkfd_norm if not unicodedata.combining(c)])
                        #a = unicodedata.normalize('NFD', a).encode('ascii', 'ignore')
                        #a = unidecode(a)
                        if a not in BaudotMurrayCode._valid_convert_chars:
                            a = '?'
                ret += a
            except:
                pass
                        
        return ret

    # -----

    @staticmethod
    def do_flip_bits(code: bytes) -> bytes:
        ret = bytearray()

        for b in code:
            rb = 0
            if b & 1:
                rb |= 16
            if b & 2:
                rb |= 8
            if b & 4:
                rb |= 4
            if b & 8:
                rb |= 2
            if b & 16:
                rb |= 1
            ret.append(rb)

        return ret

    # =====

    def __init__(self, loop_back:bool=False, coding:int=0, flip_bits=False, character_duration=0.15, show_BuZi:int=2):
        self._mode = None   # 0=LTRS 1=FIGS
        self._flip_bits = flip_bits
        self._loop_back = loop_back
        self._show_all_BuZi = show_BuZi
        self._loop_back_eat_bytes = 0
        self._loop_back_expire_time = 0
        self._character_duration = character_duration
        if coding == self.CODING_US:
            self._LUT_BM2A = self._LUT_BM2A_US
            self._LUT_BMsw = self._LUT_BMsw_US
        elif coding == self.CODING_MKT2:
            self._LUT_BM2A = self._LUT_BM2A_MKT2
            self._LUT_BMsw = self._LUT_BMsw_MKT2
        else:
            self._LUT_BM2A = self._LUT_BM2A_ITA2
            self._LUT_BMsw = self._LUT_BMsw_ITA2

    # -----

    def reset(self):
        self._ModeA2BM = None   # 0=LTRS 1=FIGS

    # -----

    def encodeA2BM(self, ascii:str) -> bytes:
        ''' convert an ASCII string to a list of baudot-murray-coded bytes '''
        ret = bytearray()

        if not isinstance(ascii, str):
            ascii = str(ascii)

        ascii = ascii.upper()

        if self._mode is None:
            self._mode = 0  # letters
            ret.append(self._LUT_BMsw[self._mode])

        for a in ascii:
            try:  # symbol in current layer?
                nm = self._mode
                b = self._LUT_BM2A[nm].index(a)
                ret.append(b)
                if b in self._LUT_BMsw:  # explicit Bu or Zi
                    self._mode = self._LUT_BMsw.index(b)
            except ValueError:
                try:  # symbol in other layer?
                    nm += 1
                    if nm >= len(self._LUT_BM2A):
                        nm = 0
                    b = self._LUT_BM2A[nm].index(a)
                    ret.append(self._LUT_BMsw[nm])
                    ret.append(b)
                    self._mode = nm
                except ValueError:
                    try:  # symbol in other layer?
                        nm += 1
                        if nm >= len(self._LUT_BM2A):
                            nm = 0
                        b = self._LUT_BM2A[nm].index(a)
                        ret.append(self._LUT_BMsw[nm])
                        ret.append(b)
                        self._mode = nm
                    except:  # symbol not found -> ignore
                        pass
            except:  # unknown -> ignore
                pass

        if ret and self._flip_bits:
            ret = self.do_flip_bits(ret)

        if self._loop_back:
            l = len(ret)
            self._loop_back_eat_bytes += l
            time_act = time.time()
            if self._loop_back_expire_time < time_act:
                self._loop_back_expire_time = time_act
            self._loop_back_expire_time += l * self._character_duration

        return ret

    # -----

    def decodeBM2A(self, code:bytes) -> str:
        ''' convert a list/bytearray of baudot-murray-coded bytes to an ASCII string '''
        ret = ''

        if self._flip_bits:
            code = self.do_flip_bits(code)

        for b in code:
            if self._loop_back and self._loop_back_eat_bytes:
                if time.time()-self._loop_back_expire_time > 6:   # about 40 characters
                    self._loop_back_eat_bytes = 0
                else:
                    self._loop_back_eat_bytes -= 1
                    #if b == 2:
                    #    print(self._loop_back_eat_bytes, time.time()-self._loop_back_expire_time)   # debug
                    continue

            try:
                if b in self._LUT_BMsw:
                    mode = self._LUT_BMsw.index(b)
                    if self._mode != mode:
                        self._mode = mode
                        if self._show_BuZi == 0: # no BuZi
                            continue
                    if self._show_BuZi <= 1: # explicit BuZi
                        continue

                if b >= 0x20:
                    ret += '{#' + hex(b)[2:] + '}'
                elif self._mode is None:
                    ret += '{?'
                    ret += self._LUT_BM2A[0][b]
                    ret += self._LUT_BM2A[1][b]
                    ret += '}'
                else:
                    ret += self._LUT_BM2A[self._mode][b]
            except:
                ret += '{!}'  # debug

        return ret

#######
