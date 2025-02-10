#!/usr/bin/python3
"""
Telex Device - Master-Control-Module (MCP)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.1.0"

import time
import os
import sys
import random

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import txCLI
from txDevMCP_escape_texts import escape_texts
from txWatchdog import Watchdog

# Timeout in ready-to-dial state in sec
DIAL_TIMEOUT = 55  # 45sec
# Timeout in ready-to-dial state in sec
ACTIVE_TIMEOUT = 3*60  # 3min

# offline, teleprinter power off
S_SLEEPING = -10
# offline, teleprinter power on
S_OFFLINE = 0
# dial mode
S_DIALING = 10
# online, printer start requested
S_ACTIVE_INIT = 20
# online, printer running
S_ACTIVE_READY = 21
# online, printer startup failed
S_ACTIVE_NO_P = 29
# punch tape font mode
S_ACTIVE_FONT = 22

#######

class TelexMCP(txBase.TelexBase):
    _fontstr = {'A': 'VSSV', 'B': '<YYR', 'C': 'CZZZ', 'D': '<ZZC', 'E': '<YYZ', 'F': '<SSE', 'G': 'CZYX', 'H': '<  <', 'I': 'Z<Z', 'J': '\rTZK', 'K': '< RZ', 'L': '<TTT', 'M': '<\n \n<', 'N': '<\n <', 'O': 'CZZZC', 'P': '<SS\n', 'Q': 'CZBV', 'R': '<SFL', 'S': 'LYYD', 'T': 'EE<EE', 'U': 'KTTK', 'V': 'U\rT\rU', 'W': '<\rI\r<', 'X': 'ZR RZ', 'Y': 'E\nM\nE', 'Z': 'ZBYWZ', '0': 'CZZC', '1': 'L<T', '2': 'BYYL', '3': 'ZYYR', '4': 'U V ', '5': 'UYYD', '6': 'NPYD', '7': 'EBSA', '8': 'RYYR', '9': 'LYFI', '.': 'OO', ',': 'ON', ';': 'GR', '+': '  <  ', '-': '    ', '*': 'YC CY', '/': 'T\r \nE', '=': 'RRRR', '(': 'CZ', ')': 'ZC', '?': 'EYY\n', "'": 'AA', ' ': '°°', '': '°', '\r': ' RZZ', '<': ' RZZ', '\n': 'YYYYY', '|': 'YYYYY'}
    _fontsep = '°'


    def __init__(self, **params):
        super().__init__()

        self.id = 'MCP'
        self.params = params

        self._WRU_ID = params.get('wru_id', '')
        self._WRU_replace_always = params.get('wru_replace_always', False)
        self._continue_with_no_printer = params.get('continue_with_no_printer', True)
        # Power off delay: Wait this many seconds after ESC-Z to turn
        # teleprinter power off
        self._power_off_delay = params.get('power_off_delay', 20)
        # Power button timeout: After ESC-PT, wait this many seconds to turn
        # teleprinter power off again
        self._power_button_timeout = params.get('power_button_timeout', 5*60)
        self._welcome_msg = params.get('welcome_msg', True)
        
        self._rx_buffer = []

        self._state = S_SLEEPING
        self._dial_number = ''
        # Default dial timeout to 2.0 s like i-Telex; set to '+' for plus
        # dialling
        dial_timeout = params.get('dial_timeout', 2.0)
        if dial_timeout == '+':
            dial_timeout = sys.maxsize
        else:
            try:
                dial_timeout = float(dial_timeout)
            except (ValueError, TypeError):
                dial_timeout = 2.0
            if not 0.0 <= dial_timeout < DIAL_TIMEOUT:
                l.warning("Invalid dialling timeout, falling back to default: " + repr(dial_timeout))
                dial_timeout = 2.0
        self._dial_timeout = dial_timeout

        self._wd = Watchdog()
        self._wd.init('ACTIVE', self._stop_watchdog_callback, ACTIVE_TIMEOUT)
        self._wd.init('DIAL', self._dial_watchdog_callback, self._dial_timeout, DIAL_TIMEOUT)
        self._wd.init('PRINTER', self._printer_start_watchdog_callback, 5)
        self._wd.init('POWER', self._power_watchdog_callback, self._power_off_delay)
        self._wd.init('WRU', self._WRU_watchdog_callback, 2)
        #self._wd.init('WELCOME', self._welcome_watchdog_callback, 1)

        self.cli = txCLI.CLI(**params)
        self.cli_text = ''
        self.cli_enable = False

        self._on_by_PT = False

        self._hand_type_buffer = []
        self._hand_type_wait = -1

        self._last_char_was_cr = False
        self._cr_count = 0

    def __del__(self):
        super().__del__()


    def exit(self):
        pass


    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)


    def write(self, a:str, source:str):
        if len(a) > 1 and a[0] == '\x1b':
            a = a[1:]
            if a == '1T':   # 1T
                if self._state <= S_OFFLINE:
                    a = 'AT'
                elif self._state == S_DIALING:
                    a = 'LT'
                else:
                    a = 'ST'

            if a == 'AT':   # AT
                self._set_state(S_DIALING, True)
                return True

            if a == 'ST':   # ST
                if self._state > S_OFFLINE:         # don't wake up from ZZ by pressing "ST"  # rowo
                    self._set_state(S_OFFLINE, True)
                return True

            if a == 'LT':   # LT
                self._set_state(S_ACTIVE_INIT, True)
                return True

            if a == 'PT':   # PT
                if self._state == S_SLEEPING:
                    self._set_state(S_OFFLINE, True)
                    self._wd.restart('POWER', self._power_button_timeout)
                    self._on_by_PT = True
                else:
                    self._set_state(S_OFFLINE, True)
                    self._wd.restart('POWER', 1)
                return True

            if a == 'Z':   # stop motor
                self._set_state(S_OFFLINE)

            if a == 'ZZ':   # sleeping
                self._set_state(S_SLEEPING)

            if a == 'A':   # start printer motor
                self._set_state(S_ACTIVE_INIT)

            if a == 'AA':   # printer ready
                self._set_state(S_ACTIVE_READY)

            if a == 'WB':   # start dialing
                self._set_state(S_DIALING)

            if a.startswith('~') or a.startswith('^'):   # printer buffer feedback
                # Reset ACTIVE watchdog only if we're still online, to prevent
                # re-enabling teleprinter power later
                if self._state > S_OFFLINE:
                    self._wd.restart('ACTIVE')
                # If we're already in S_OFFLINE after a connection terminated,
                # but have still data to print, avoid cutting power too early
                # by resetting the timer on each ESC-~. On empty printer
                # buffer, ESC-~'s will stop.
                if self._wd.is_active('POWER'):
                    if self._on_by_PT:
                        self._wd.restart('POWER', self._power_button_timeout)
                    else:
                        self._wd.restart('POWER')
                # Also reset WRU timer to avoid the fallback WRU responder from
                # triggering before the teleprinter's has had a chance
                if self._wd.is_active('WRU'):
                    self._wd.restart('WRU')
                return

            if a == '...':   # printer busy
                pass

            if a == 'FONT':   # set to font mode
                if self._state == S_ACTIVE_FONT:
                    self._set_state(S_ACTIVE_READY)
                else:
                    self._set_state(S_ACTIVE_FONT)
                return True

            if a in escape_texts:
                self._rx_buffer.extend(list(escape_texts[a]))   # send text
                return True

            if a == 'DATE':   # current date and time
                text = time.strftime("%Y-%m-%d  %H:%M", time.localtime()) + '\r\n'
                self._rx_buffer.extend(list(text))   # send text
                return True

            if a == 'I':   # welcome as server
                # The welcome banner itself has a fixed total length of 24 characters:
                text= '<<<\r\n'
                if self._welcome_msg:
                    text += time.strftime("%d.%m.%Y  %H:%M", time.localtime()) + '\r\n' 
                #if self._WRU_ID:
                #    text += self._WRU_ID   # send back device id
                #else:
                #    text += '#'
                self._rx_buffer.extend(list(text))   # send text
                if source == 'iTs':
                    # Send command to inform ITelexSrv that the welcome banner has
                    # been queued completely (unlocks non-command reads from
                    # ITelexSrv)
                    self._rx_buffer.append('\x1bWELCOME')
                return True

            if a == 'CLI':   # command line interface
                l.info("Start CLI")
                self.enable_cli(True)
                return True

            if a.startswith('READ'):
                self.read_file(a[5:])

            if a == 'EXIT':   # leave program
                l.info("ESC-EXIT")
                #self._set_state(S_OFFLINE)
                raise(SystemExit('EXIT'))

            if a == 'T':   # hand type simulator
                if self._hand_type_wait >= 0:
                    self._hand_type_wait = -1
                else:
                    self._hand_type_wait = 40   # 2 sec delay

        else:   # single char -------------------------------------------------

            # reset watchdog timers
            if self._state > S_OFFLINE:
                self._wd.restart('ACTIVE')

            # Insert text files into stream by typing five times or more  'WR' (carriage return)
            # followed by a single number as file name ; 10 files are selectable.
            # The files must reside in a subdirectory 'read' of piTelex and have '.txt' as extension.
            # '0' --> '...piTelex/read/0.txt',   ....    '9' --> '...piTelex/read/9.txt'  

            if a == '\r': 
                if source not in ('iTs', 'iTc'): 	#only count locally typed '\r'
                    if self._last_char_was_cr:
                        self._cr_count += 1
                    else:
                        self._cr_count = 1
                        self._last_char_was_cr = True
            else:
                if a != '>':                        # ignore "Zi"
                    if self._cr_count >= 5 and self._last_char_was_cr:  
                        if a in '0123456789':             	#Filename follows immediately after multiple 'WR'          
                            self.read_file(a)
                    self._last_char_was_cr = False
               

            # command line interface
            if self.cli_enable:
                if a in ' \n+?':
                    ans = self.cli.command(self.cli_text)
                    self._rx_buffer.extend(list(ans))
                    if ans == 'BYE\r\n':
                        self.enable_cli(False)
                        self._rx_buffer.append('\x1bZ')
                    self.cli_text = ''
                else:
                    self.cli_text += a
                    return

            # print punch tape characters
            if self._state == S_ACTIVE_FONT:   #
                f = self._fontstr.get(a, None)
                if f:
                    f += self._fontsep
                    self._rx_buffer.extend(list(f))   # send back font pattern
                return True

            # WRU request to teletype
            if self._WRU_ID and a == '#':   # found 'Wer da?' / 'WRU'
                if self._WRU_replace_always:
                    self._WRU_watchdog_callback(None)
                    return True
                self._wd.restart('WRU')
                return None

            if self._wd.is_active('WRU'):
                if a in '<°':   # found Bu or Null
                    self._wd.restart('WRU')   #  -> hardware WRU-unit has no drum -> wait for end of trans. and send soft-WRU
                else:
                    self._wd.disable('WRU')   #  -> hardware WRU-unit has answered


            if self._state == S_DIALING:
                #if a == '0':   # hack!!!! to test the pulse dial
                #    self._send_control_sequence('A')   # send text

                # A digit or +/- is being dialled; record digit and trigger dial
                # thread to check
                if a.isalnum() or a == '-':
                    self._dial_number += a
                    self._wd.restart('DIAL')
                    if self._dial_timeout <= 0:
                        self._dial_watchdog_callback('DIAL_TRY')
                elif a == '+' and self._dial_timeout == sys.maxsize:
                    self._wd.disable('DIAL')
                    self._dial_watchdog_callback('DIAL_PLUS')
                else:
                    # Invalid data for dial mode, except it's an error printed by
                    # txDevITelexClient
                    if source == 'iTc':
                        # Error message, print
                        return None
                    else:
                        # Invalid data, discard
                        return True

    # -----

    def idle20Hz(self):
        self._wd.process()

        # hand type simulator
        if self._hand_type_wait >= 0:
            if self._hand_type_wait == 0:
                if not self._hand_type_buffer:
                    self._hand_type_buffer = list(escape_texts['LOREM'])
                a = self._hand_type_buffer.pop(0)
                self._rx_buffer.append(a)   # send text
                self._hand_type_wait = int(random.random()**2.0 * 5 + 2)   # emulate human typing waits
                if a in ('\r', '\n'):
                    self._hand_type_wait += 7
                if a in (' ', '.', ',', '<', '>'):
                    self._hand_type_wait += 1
            else:
                self._hand_type_wait -= 1

    def idle2Hz(self):
        if self._state == S_ACTIVE_NO_P and self._continue_with_no_printer:
            # Fake buffer feedback in case the teleprinter failed
            self._send_control_sequence('~0')

    # =====

    def _set_state(self, new_state:int, broadcast_state:bool=False):
        ''' set new state and change hardware properties '''
        if self._state == new_state:
            return
        l.debug('set_state {} -> {}'.format(self._state, new_state))

        # leaving old state

        if self._state == S_SLEEPING:
            self._send_control_sequence('TP1')   # send power on

        # enter new state

        if new_state == S_SLEEPING:
            self._send_control_sequence('TP0')   # send power off
            self._wd.disable('POWER')

            if broadcast_state:
                self._send_control_sequence('ZZ')

        elif new_state == S_OFFLINE:
            self._wd.disable('ACTIVE')
            self._wd.disable('DIAL')
            self._wd.disable('PRINTER')
            if self._on_by_PT:
                self._wd.restart('POWER', self._power_button_timeout)
            else:
                self._wd.restart('POWER')
            self.enable_cli(False)

            if broadcast_state:
                self._send_control_sequence('Z')

        elif new_state == S_DIALING:
            self._dial_number = ''
            self._wd.disable('ACTIVE')
            self._wd.restart('DIAL', 0)
            self._wd.disable('POWER')

            if broadcast_state:
                self._send_control_sequence('WB')

        elif new_state == S_ACTIVE_INIT:
            if self._state > S_ACTIVE_INIT:
                return
            self._wd.restart('ACTIVE')
            self._dial_number = '' # Important only on instant dialling
            self._wd.disable('DIAL')
            self._wd.restart('PRINTER')
            self._wd.disable('POWER')
            l.info("Printer start timer enabled")

            if broadcast_state:
                self._send_control_sequence('A')

        elif new_state == S_ACTIVE_READY or new_state == S_ACTIVE_NO_P:
            self._wd.restart('ACTIVE')
            self._wd.disable('DIAL')
            self._wd.disable('PRINTER')
            self._wd.disable('POWER')

            if broadcast_state:
                self._send_control_sequence('AA')

        elif new_state == S_ACTIVE_FONT:
            pass

        self._state = new_state

    # =====

    def enable_cli(self, enable:bool):
        if enable:
            self.cli_enable = True
            self.cli_text = ''
            self._set_state(S_ACTIVE_INIT, True)
            ans = self.cli.command('WHOAMI')
            self._rx_buffer.extend(list(ans))
        else:
            self.cli_enable = False

    # -----

    def send_abort(self, last_words:str=None):
        if last_words:
            self._set_state(S_ACTIVE_INIT, True)
            #self._set_state(S_ACTIVE_READY, True)
            self._rx_buffer.extend(list(last_words))
        self._set_state(S_OFFLINE, True)

    # -----

    def _send_control_sequence(self, cmd:str):
        self._rx_buffer.append('\x1b'+cmd)

    # -----

    def read_file(self, file_name:str):
        base_name = os.path.join('read', file_name.lower())
        try:
            name = self.read_file_exist(base_name, ('txt',))
            text = ''

            if name:
                with open(name, mode="r", encoding="utf-8") as fp:
                    text = fp.read()
                    text = text.replace('\n', '\r\n')
                    text = txCode.BaudotMurrayCode.translate(text)

            name = self.read_file_exist(base_name, ('pix', 'pox'))
            if name:
                with open(name, 'rb') as fp:
                    text = fp.read().decode('ASCII', errors='ignore')
                    for us, eu in (('&','8'), ('#','M'), ('$','S'), ('"',"'"), (';',','), ('!','1'), ('\x1A','')):
                        text = text.replace(us, eu)
                    text = txCode.BaudotMurrayCode.translate(text)
                    if True:
                        mc = txCode.BaudotMurrayCode()
                        bintext = mc.encodeA2BM(text)
                        with open(base_name+'_.bin', 'wb') as wfp:
                            wfp.write(bintext)

            name = self.read_file_exist(base_name, ('bin', 'ls'))
            if name:
                with open(name, 'rb') as fp:
                    bintext = fp.read()
                    mc = txCode.BaudotMurrayCode(flip_bits=name.endswith('ls'))
                    text = mc.decodeBM2A(bintext)

            if text:
                self._rx_buffer.extend(list(text))
                l.info("Read file: {!r} ({} chars)".format(name, len(text)))

        except:
            l.error("Error in read file")

    # -----

    def read_file_exist(self, base_name:str, extensions:list):
        for extension in extensions:
            name = base_name + '.' + extension
            if os.path.isfile(name):
                return name

    # =====

    def _stop_watchdog_callback(self, name:str):
        self.write('\x1bST', 'wdg')

    # -----

    def _dial_watchdog_callback(self, name:str):
        #print('<<<', name, self._dial_number, '>>>')
        if name.endswith('ABORT'):
            #self.write('\x1bST', 'wdg')
            self.send_abort('<<<   ABORT   ')
        elif self._dial_number:
            if self._dial_number.startswith('00'):
                if self._dial_number == '000':   # 000 - local mode
                    self._set_state(S_ACTIVE_INIT, True)
                    self._dial_number = ''
                elif self._dial_number == '009':   # 009 - command line interface
                    self.enable_cli(True)
                    self._dial_number = ''
            else:
                if self._dial_timeout > 0 or name.endswith('DIREKT'):
                    self._send_control_sequence('#' + self._dial_number)
                    self._dial_number = ''
                else:
                    self._send_control_sequence('#!' + self._dial_number)


    def _printer_start_watchdog_callback(self, name:str):
        if self._continue_with_no_printer:
            # On teleprinter timeout, send fake ESC-AA
            l.warning("Printer start attempt timed out, feedback simulation enabled")
            self._set_state(S_ACTIVE_NO_P, True)
        else:
            l.warning("Printer start attempt timed out")
            self.send_abort()

    # -----

    def _power_watchdog_callback(self, name:str):
        if self._state != S_OFFLINE:
            self.send_abort()
        self._set_state(S_SLEEPING, True)
        self._on_by_PT = False

    # -----

    def _welcome_watchdog_callback(self, name:str):
        pass

    # -----

    def _WRU_watchdog_callback(self, name:str):
        self._rx_buffer.extend(list('<\r\n' + self._WRU_ID))   # send back device id
        l.info("Sending software WRU response: {!r}".format(self._WRU_ID))

#######

