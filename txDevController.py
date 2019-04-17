#!/usr/bin/python3
"""
Telex Device - System-Controller
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread
import time

import txBase

#######

class watchdog():
    def __init__(self):
        self._wds = {}
        pass

    def init(self, name:str, timer:int, action_list, action_char:str):
        wd = {}
        wd['time_reset'] = None
        wd['time_offset'] = timer 
        wd['action_list'] = action_list
        wd['action_char'] = action_char
        self._wds[name] = wd

    def reset(self, name:str):
        self._wds[name]['time_reset'] = time.time()

    def disable(self, name:str):
        self._wds[name]['time_reset'] = None

    def process(self):
        time_act = time.time()

        for name, wd in self._wds.items():
            if wd['time_reset']:
                if  time_act > (wd['time_reset'] + wd['time_offset']):
                    wd['time_reset'] = None
                    wd['action_list'].append(wd['action_char'])

#######

class TelexController(txBase.TelexBase):
    _fontstr = {'A': 'VSSV', 'B': '[YYR', 'C': 'CZZZ', 'D': '[ZZC', 'E': '[YYZ', 'F': '[SSE', 'G': 'CZYX', 'H': '[  [', 'I': 'Z[Z', 'J': '<TZK', 'K': '[ RZ', 'L': '[TTT', 'M': '[|M|[', 'N': '[| [', 'O': 'CZZZC', 'P': '[SS|', 'Q': 'CZBV', 'R': '[SFL', 'S': 'LYYD', 'T': 'EE[EE', 'U': 'KTTK', 'V': 'U<T<U', 'W': '[<I<[', 'X': 'ZR RZ', 'Y': 'E|M|E', 'Z': 'ZBYWZ', '0': 'CZZC', '1': 'L[T', '2': 'BYYL', '3': 'ZYYR', '4': 'U V ', '5': 'UYYD', '6': 'NPYD', '7': 'EBSA', '8': 'RYYR', '9': 'LYFI', '.': 'OO', ',': 'ON', ';': 'GR', '+': '  [  ', '-': '    ', '*': 'YC CY', '/': 'T< |E', '=': 'RRRR', '(': 'CZ', ')': 'ZC', '?': 'EYY|', "'": 'AA', ' ': '~~', '': '~', '\r': ' RZZ', '<': ' RZZ', '\n': 'YYYYY', '|': 'YYYYY'}
    _fontsep = '~'


    def __init__(self, **params):
        super().__init__()


        self.id = '^'
        self.params = params

        self.device_id = params.get('wru_id', '')

        self._rx_buffer = []
        self._mx_buffer = []

        self._font_mode = False
        self._dial_mode = False
        self._dial_number = ''

        self._wd = watchdog()
        self._wd.init('ONLINE', 180, self._rx_buffer, '\x1bZ')

        self._run = True
        self._tx_thread = Thread(target=self.thread_memory, name='CtrlMem')
        self._tx_thread.start()


    def __del__(self):
        self._run = False
        super().__del__()
    

    def exit(self):
        self._run = False


    def read(self) -> str:
        ret = ''


        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bAT':   # AT
                self._rx_buffer.append('\x1bWB')   # send text
                self._dial_mode = True
                self._dial_number = ''
                self._wd.reset('ONLINE')
                return True

            if a == '\x1bST':   # ST
                self._rx_buffer.append('\x1bZ')   # send text
                self._dial_mode = False
                self._wd.disable('ONLINE')
                return True

            if a == '\x1bLT':   # LT
                self._rx_buffer.append('\x1bA')   # send text
                self._dial_mode = False
                self._wd.reset('ONLINE')
                return True

            if a == '\x1bZ':   # stop motor
                self._dial_mode = False
                self._wd.disable('ONLINE')
            if a == '\x1bA':   # start motor
                self._dial_mode = False
                self._wd.reset('ONLINE')


            if a == '\x1bFONT':   # set to font mode
                self._font_mode = not self._font_mode
                return True


            if a == '\x1bLOREM':   # print LOREM IPSUM (460 characters = 69sec@50baud)
                self._rx_buffer.extend(list('\r\nLOREM IPSUM DOLOR SIT AMET, CONSECTETUR ADIPISICI ELIT,\r\nSED EIUSMOD TEMPOR INCIDUNT UT LABORE ET DOLORE MAGNA ALIQUA.\r\nUT ENIM AD MINIM VENIAM, QUIS NOSTRUD EXERCITATION ULLAMCO\r\nLABORIS NISI UT ALIQUID EX EA COMMODI CONSEQUAT. QUIS AUTE IURE\r\nREPREHENDERIT IN VOLUPTATE VELIT ESSE CILLUM DOLORE EU FUGIAT\r\nNULLA PARIATUR. EXCEPTEUR SINT OBCAECAT CUPIDITAT NON PROIDENT,\r\nSUNT IN CULPA QUI OFFICIA DESERUNT MOLLIT ANIM ID EST LABORUM.\r\n'))   # send text
                return True

            if a == '\x1bRY':   # print RY pattern (64 characters = 10sec@50baud)
                self._rx_buffer.extend(list('RYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRY'))   # send text
                return True

            if a == '\x1bFOX':   # print RY pattern (64 characters = 10sec@50baud)
                self._rx_buffer.extend(list('THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG'))   # send text
                return True

            if a == '\x1bABC':   # print ABC pattern (51 characters = 7.6sec@50baud)
                self._rx_buffer.extend(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890 .,-+=/()?\'%'))   # send text
                return True

            if a == '\x1bLOGO':   # print piTelex logo (380 characters = 57sec@50baud)
                self._rx_buffer.extend(list('''
-----------------------------------------------------
      OOO   OOO  OOOOO  OOOO  O     OOOO  O   O
      O  O   O     O    O     O     O      O O
      OOO    O     O    OOO   O     OOO     O
.....................................................
      O      O     O    O     O     O      O O
      O     OOO    O    OOOO  OOOO  OOOO  O   O
-----------------------------------------------------
'''))   # send text
                return True

            if a == '\x1bTEST':   # print test pattern (546 characters = 82sec@50baud)
                self._rx_buffer.extend(list('''
.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.
-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-
=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=
X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X
=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=
-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-'''))   # send text
                return True


            if a[:3] == '\x1bM=':   # set memory text
                self._mx_buffer.extend(list(a[3:]))   # send text
                return True

            if a == '\x1bMC':   # clear memory text
                self._mx_buffer = []
                return True


            if a == '\x1bT':   # actual time
                text = time.strftime("%Y-%m-%d  %H:%M", time.localtime()) + '\r\n'
                self._rx_buffer.extend(list(text))   # send text
                return True

            if a == '\x1bI':   # welcome as server
                text = '[[[\r\n' + time.strftime("%d.%m.%Y  %H:%M", time.localtime()) + '\r\n'
                #if self.device_id:
                #    text += self.device_id   # send back device id
                #else:
                #    text += '#'
                self._rx_buffer.extend(list(text))   # send text
                return True


            if a == '\x1bEXIT':   # leave program
                raise(SystemExit('EXIT'))


        self._wd.reset('ONLINE')

        if self._font_mode:   # 
            f = self._fontstr.get(a, None)
            if f:
                f += self._fontsep
                self._rx_buffer.extend(list(f))   # send back font pattern
            return True


        if self.device_id and a == '#':   # found 'Wer da?' / 'WRU'
            self._rx_buffer.extend(list('[\r\n' + self.device_id))   # send back device id
            return True


        if self._dial_mode:
            #if a == '0':   # hack!!!! to test the pulse dial
            #    self._rx_buffer.append('\x1bA')   # send text
            self._dial_number += a
            self._rx_buffer.append('\x1b#'+self._dial_number)   # send text


    # -----

    def idle20Hz(self):
        self._wd.process()

    # =====
    
    def thread_memory(self):
        while self._run:
            #LOG('.')
            if self._mx_buffer:
                a = self._mx_buffer.pop(0)
                self._rx_buffer.append(a)
            time.sleep(0.15)
        
#######

