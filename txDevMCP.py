#!/usr/bin/python3
"""
Telex Device - Master-Control-Module (MCP)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.1.0"

from threading import Thread
import time

import txBase
import txCLI

#######

escape_texts = {
    '\x1bRY':   # print RY pattern (64 characters = 10sec@50baud)
        'RY'*32,
    '\x1bFOX':   # print RY pattern (? characters = 10sec@50baud)
        'THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG',
    '\x1bPELZE':   # print RY pattern (? characters = 10sec@50baud)
        'KAUFEN SIE JEDE WOCHE VIER GUTE BEQUEME PELZE XY 1234567890',
    '\x1bABC':   # print ABC pattern (51 characters = 7.6sec@50baud)
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890 .,-+=/()?\'%',
    '\x1bA1':   # print Bi-Zi-change pattern (? characters = 7.6sec@50baud)
        'A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z%',
    '\x1bLOREM':   # print LOREM IPSUM (460 characters = 69sec@50baud)
        '''\r
LOREM IPSUM DOLOR SIT AMET, CONSECTETUR ADIPISICI ELIT,\r
SED EIUSMOD TEMPOR INCIDUNT UT LABORE ET DOLORE MAGNA ALIQUA.\r
UT ENIM AD MINIM VENIAM, QUIS NOSTRUD EXERCITATION ULLAMCO\r
LABORIS NISI UT ALIQUID EX EA COMMODI CONSEQUAT. QUIS AUTE IURE\r
REPREHENDERIT IN VOLUPTATE VELIT ESSE CILLUM DOLORE EU FUGIAT\r
NULLA PARIATUR. EXCEPTEUR SINT OBCAECAT CUPIDITAT NON PROIDENT,\r
SUNT IN CULPA QUI OFFICIA DESERUNT MOLLIT ANIM ID EST LABORUM.\r
''',
    '\x1bLOGO':   # print piTelex logo (380 characters = 57sec@50baud)
        '''\r
-----------------------------------------------------\r
      OOO   OOO  OOOOO  OOOO  O     OOOO  O   O\r
      O  O   O     O    O     O     O      O O\r
      OOO    O     O    OOO   O     OOO     O\r
.....................................................\r
      O      O     O    O     O     O      O O\r
      O     OOO    O    OOOO  OOOO  OOOO  O   O\r
-----------------------------------------------------\r
''',
    '\x1bTEST':   # print test pattern (546 characters = 82sec@50baud)
        '''\r
.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.\r
-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-\r
=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=\r
X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X\r
=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=\r
-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-''',
}

#######

class watchdog():
    def __init__(self):
        self._wds = {}

    def init(self, name:str, timer:int, callback):
        wd = {}
        wd['time_reset'] = None
        wd['time_offset'] = timer
        wd['callback'] = callback
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
                    wd['callback'](name)

#######

class TelexMCP(txBase.TelexBase):
    _fontstr = {'A': 'VSSV', 'B': '<YYR', 'C': 'CZZZ', 'D': '<ZZC', 'E': '<YYZ', 'F': '<SSE', 'G': 'CZYX', 'H': '<  <', 'I': 'Z<Z', 'J': '<TZK', 'K': '< RZ', 'L': '<TTT', 'M': '<|M|<', 'N': '<| <', 'O': 'CZZZC', 'P': '<SS|', 'Q': 'CZBV', 'R': '<SFL', 'S': 'LYYD', 'T': 'EE<EE', 'U': 'KTTK', 'V': 'U<T<U', 'W': '<<I<<', 'X': 'ZR RZ', 'Y': 'E|M|E', 'Z': 'ZBYWZ', '0': 'CZZC', '1': 'L<T', '2': 'BYYL', '3': 'ZYYR', '4': 'U V ', '5': 'UYYD', '6': 'NPYD', '7': 'EBSA', '8': 'RYYR', '9': 'LYFI', '.': 'OO', ',': 'ON', ';': 'GR', '+': '  <  ', '-': '    ', '*': 'YC CY', '/': 'T< |E', '=': 'RRRR', '(': 'CZ', ')': 'ZC', '?': 'EYY|', "'": 'AA', ' ': '~~', '': '~', '\r': ' RZZ', '<': ' RZZ', '\n': 'YYYYY', '|': 'YYYYY'}
    _fontsep = '~'


    def __init__(self, **params):
        super().__init__()


        self.id = '^'
        self.params = params

        self.device_id = params.get('wru_id', '')

        self._rx_buffer = []
        self._mx_buffer = []

        self._font_mode = False
        self._mode = 'Z'
        self._dial_number = ''

        self._wd = watchdog()
        self._wd.init('ONLINE', 180, self._watchdog_callback)

        self.cli = txCLI.CLI(**params)
        self.cli_text = ''
        self.cli_enable = False

        #self._run = True
        #self._tx_thread = Thread(target=self.thread_memory, name='CtrlMem')
        #self._tx_thread.start()


    def __del__(self):
        #self._run = False
        super().__del__()


    def exit(self):
        #self._run = False
        pass


    def read(self) -> str:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1b1T':   # 1T
                if self._mode == 'Z':
                    a = '\x1bAT'
                elif self._mode == 'WB':
                    a = '\x1bLT'
                else:
                    a = '\x1bST'

            if a == '\x1bAT':   # AT
                self._rx_buffer.append('\x1bWB')   # send text
                self._mode = 'WB'
                self._dial_number = ''
                self._wd.reset('ONLINE')
                return True

            if a == '\x1bST':   # ST
                self._rx_buffer.append('\x1bZ')   # send text
                self._mode = 'Z'
                self._wd.disable('ONLINE')
                return True

            if a == '\x1bLT':   # LT
                self._rx_buffer.append('\x1bA')   # send text
                self._mode = 'A'
                self._wd.reset('ONLINE')
                return True

            if a == '\x1bZ':   # stop motor
                self._mode = 'Z'
                self._wd.disable('ONLINE')

            if a == '\x1bA':   # start motor
                self._mode = 'A'
                self._wd.reset('ONLINE')


            if a == '\x1bFONT':   # set to font mode
                self._font_mode = not self._font_mode
                return True


            if a in escape_texts:
                self._rx_buffer.extend(list(escape_texts[a]))   # send text
                return True


            #if a[:3] == '\x1bM=':   # set memory text
            #    self._mx_buffer.extend(list(a[3:]))   # send text
            #    return True

            #if a == '\x1bMC':   # clear memory text
            #    self._mx_buffer = []
            #    return True


            if a == '\x1bDATE':   # actual date and time
                text = time.strftime("%Y-%m-%d  %H:%M", time.localtime()) + '\r\n'
                self._rx_buffer.extend(list(text))   # send text
                return True

            if a == '\x1bI':   # welcome as server
                text = '<<<\r\n' + time.strftime("%d.%m.%Y  %H:%M", time.localtime()) + '\r\n'
                #if self.device_id:
                #    text += self.device_id   # send back device id
                #else:
                #    text += '#'
                self._rx_buffer.extend(list(text))   # send text
                return True

            if a == '\x1bCLI':   # welcome as server
                self.enable_cli(True)
                return True

            if a == '\x1bEXIT':   # leave program
                raise(SystemExit('EXIT'))


        else:   # single char

            self._wd.reset('ONLINE')

            if self.cli_enable:
                if a in ' \n+?':
                    ans = self.cli.command(self.cli_text)
                    if ans == 'BYE\r\n':
                        self.enable_cli(False)
                    self._rx_buffer.extend(list(ans))
                    self.cli_text = ''
                else:
                    self.cli_text += a
                    return

        if self._font_mode:   #
            f = self._fontstr.get(a, None)
            if f:
                f += self._fontsep
                self._rx_buffer.extend(list(f))   # send back font pattern
            return True


        if self.device_id and a == '#':   # found 'Wer da?' / 'WRU'
            self._rx_buffer.extend(list('<\r\n' + self.device_id))   # send back device id
            return True


        if self._mode == 'WB':
            #if a == '0':   # hack!!!! to test the pulse dial
            #    self._rx_buffer.append('\x1bA')   # send text
            if a.isdigit():
                self._dial_number += a
                if self._dial_number == '000':
                    self.enable_cli(True)
                    return True
                self._rx_buffer.append('\x1b#'+self._dial_number)   # send text
            else:
                return True

    # -----

    def idle20Hz(self):
        self._wd.process()

    # =====

    def _watchdog_callback(self, name:str):
        self.write('\x1bST', 'w')

    # -----

    #def thread_memory(self):
    #    while self._run:
    #        #LOG('.')
    #        if self._mx_buffer:
    #            a = self._mx_buffer.pop(0)
    #            self._rx_buffer.append(a)
    #        time.sleep(0.15)

    # =====

    def enable_cli(self, enable:bool):
        if enable:
            self.cli_enable = True
            self.cli_text = ''
            self._rx_buffer.append('\x1bA')
            ans = self.cli.command('WHOAMI')
            self._rx_buffer.extend(list(ans))
        else:
            self.cli_enable = False

#######

