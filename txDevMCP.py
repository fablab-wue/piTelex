#!/usr/bin/python3
"""
Telex Device - Master-Control-Module (MCP)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.1.0"

from threading import Thread, Event
import time

import logging
l = logging.getLogger("piTelex." + __name__)

import txBase
import txCLI

# Timeout in ready-to-dial state in sec
WB_TIMEOUT = 45
# Timeout in ready-to-dial state in sec
ONLINE_TIMEOUT = 180

#######

# Error messages, based on r874 of i-Telex source and personal conversation
# with Fred
#
# Types:
# - A: printed at the calling party during keyboard dial
# - B: sent as reject packet payload by called party
#
# Error Type Handled in  Description
# bk    A    iTxClient   dial failure (called party not found in TNS)
# nc    A    iTxClient   cannot establish TCP connection to called party
# abs   A                line disabled
# abs   B                line disabled
# occ   B    iTxSrv      line occupied
# der   B    iTxCommon   derailed: line connected, but called teleprinter
#                        not starting up
# na    B    iTxCommon   called extension not allowed
#
# B type errors are handled in txDevITelexCommon.send_reject. It defaults to
# "abs", but this error isn't used yet.

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
                    l.debug("Watchdog {!r}: {!r}".format(name, wd["callback"]))

#######

class TelexMCP(txBase.TelexBase):
    _fontstr = {'A': 'VSSV', 'B': '<YYR', 'C': 'CZZZ', 'D': '<ZZC', 'E': '<YYZ', 'F': '<SSE', 'G': 'CZYX', 'H': '<  <', 'I': 'Z<Z', 'J': '\rTZK', 'K': '< RZ', 'L': '<TTT', 'M': '<\n \n<', 'N': '<\n <', 'O': 'CZZZC', 'P': '<SS\n', 'Q': 'CZBV', 'R': '<SFL', 'S': 'LYYD', 'T': 'EE<EE', 'U': 'KTTK', 'V': 'U\rT\rU', 'W': '<\rI\r<', 'X': 'ZR RZ', 'Y': 'E\nM\nE', 'Z': 'ZBYWZ', '0': 'CZZC', '1': 'L<T', '2': 'BYYL', '3': 'ZYYR', '4': 'U V ', '5': 'UYYD', '6': 'NPYD', '7': 'EBSA', '8': 'RYYR', '9': 'LYFI', '.': 'OO', ',': 'ON', ';': 'GR', '+': '  <  ', '-': '    ', '*': 'YC CY', '/': 'T\r \nE', '=': 'RRRR', '(': 'CZ', ')': 'ZC', '?': 'EYY\n', "'": 'AA', ' ': '~~', '': '~', '\r': ' RZZ', '<': ' RZZ', '\n': 'YYYYY', '|': 'YYYYY'}
    _fontsep = '~'


    def __init__(self, **params):
        super().__init__()


        self.id = '^'
        self.params = params

        self.device_id = params.get('wru_id', '')
        self.wru_fallback = params.get('wru_fallback', False)

        self._rx_buffer = []
        self._mx_buffer = []

        self._font_mode = False
        self._mode = 'Z'
        self._dial_number = ''
        # Default dial timeout to 2.0 s like i-Telex; set to '+' for plus
        # dialling
        dial_timeout = params.get('dial_timeout', 2.0)
        if dial_timeout == '+':
            dial_timeout = None
        else:
            try:
                dial_timeout = float(dial_timeout)
            except (ValueError, TypeError):
                dial_timeout = 2.0
            if not 0.0 <= dial_timeout < WB_TIMEOUT:
                l.warning("Invalid dialling timeout, falling back to default: " + repr(dial_timeout))
                dial_timeout = 2.0
        self._dial_timeout = dial_timeout
        self._dial_change = Event()

        # Fallback WRU state
        self._fallback_wru_triggered = False

        self._wd = watchdog()
        self._wd.init('ONLINE', ONLINE_TIMEOUT, self._watchdog_callback_ST)
        self._wd.init('WB', WB_TIMEOUT, self._watchdog_callback_ST)
        self._wd.init('PRINTER', 5, lambda name: self._rx_buffer.append('\x1bACT'))

        self.cli = txCLI.CLI(**params)
        self.cli_text = ''
        self.cli_enable = False

        self._run = True
        #self._tx_thread = Thread(target=self.thread_memory, name='CtrlMem')
        #self._tx_thread.start()

        self._dial_thread = Thread(target=self.thread_dial, name='Dialler')
        self._dial_thread.start()


    def __del__(self):
        self._run = False
        super().__del__()


    def exit(self):
        self._run = False
        self._dial_change.set()


    def read(self) -> str:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        if ret == '\x1bACT' and self.wru_fallback:
            # Intercept printer timeout signal and replace by a fake ESC-ACK
            self._fallback_wru_triggered = True
            l.warning("Printer start attempt timed out, fallback WRU responder enabled")
            ret = '\x1bACK'

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
                self._wd.disable('ONLINE')
                self._wd.reset('WB')
                return True

            if a == '\x1bST':   # ST
                self._rx_buffer.append('\x1bZ')   # send text
                self._mode = 'Z'
                self._wd.disable('ONLINE')
                self._wd.disable('WB')
                self.enable_cli(False)
                return True

            if a == '\x1bLT':   # LT
                self._rx_buffer.append('\x1bA')   # send text
                self._mode = 'A'
                self._wd.reset('ONLINE')
                self._wd.disable('WB')
                return True

            if a == '\x1bZ':   # stop motor
                self._mode = 'Z'
                self._wd.disable('ONLINE')
                self._wd.disable('WB')
                self._wd.disable('PRINTER')
                self._fallback_wru_triggered = False
                self.enable_cli(False)
                
            if a == '\x1bA':   # start motor
                self._mode = 'A'
                self._wd.reset('ONLINE')
                self._dial_number = '' # Important only on instant dialling
                self._wd.disable('WB')

            # Printer start feedback code follows, which enables us to check if
            # the printer hardware has in fact been started.
            #
            # To keep this backwards compatible with other interface modules
            # not supporting this, a three-step protocol is established:
            #
            # 1. Any interface module that wishes to take part shall, upon
            #    receipt of ESC-A, send ESC-AC (check).
            #
            # 2. ESC-AC activates our printer start timer.
            #
            # 3. The interface module shall, on successful printer start, send
            #    ESC-ACK (check okay), which disables our timer. The same
            #    happens on ESC-Z.
            #
            #    On timeout, we send ESC-ACT (check timeout). Any module may
            #    evaluate this information though at present, only
            #    txDevITelexSrv does: An active incoming connection is
            #    terminated with an i-Telex "der" end packet.
            #
            #    In the future, this may be used by, e.g., a recording module
            #    which hooks a timeout to step in for an unresponsive printer
            #    and record an incoming message. For this, sequence of devices
            #    in telex.py's DEVICES list and the write method's return value
            #    are critical.

            if a == '\x1bAC':
                self._wd.reset('PRINTER')
                l.debug("Printer start timer enabled")
            elif a == '\x1bACK':
                self._wd.disable('PRINTER')
                l.debug("Printer has been started successfully, cancelling start timer")

            if a == '\x1bFONT':   # set to font mode
                self._font_mode = not self._font_mode
                return True

            if a[:2] == '\x1b~':   # still characters in printing FIFO
                self._wd.reset('ONLINE')


            if a in escape_texts:
                self._rx_buffer.extend(list(escape_texts[a]))   # send text
                return True


            #if a[:3] == '\x1bM=':   # set memory text
            #    self._mx_buffer.extend(list(a[3:]))   # send text
            #    return True

            #if a == '\x1bMC':   # clear memory text
            #    self._mx_buffer = []
            #    return True


            if a == '\x1bDATE':   # current date and time
                text = time.strftime("%Y-%m-%d  %H:%M", time.localtime()) + '\r\n'
                self._rx_buffer.extend(list(text))   # send text
                return True

            if a == '\x1bI':   # welcome as server
                # The welcome banner itself has a fixed total length of 24 characters:
                text = '<<<\r\n' + time.strftime("%d.%m.%Y  %H:%M", time.localtime()) + '\r\n'
                #if self.device_id:
                #    text += self.device_id   # send back device id
                #else:
                #    text += '#'
                self._rx_buffer.extend(list(text))   # send text
                if source == '<':
                    # Send command to inform ITelexSrv that the welcome banner has
                    # been queued completely (unlocks non-command reads from
                    # ITelexSrv)
                    self._rx_buffer.append('\x1bWELCOME')
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
                if not self.wru_fallback or self._fallback_wru_triggered:
                    self._rx_buffer.extend(list('<\r\n' + self.device_id))   # send back device id
                    l.info("Sending software WRU response: {!r}".format(self.device_id))
                    # Only "swallow" WRU when *not* acting as fallback
                    if not self._fallback_wru_triggered:
                        return True


            if self._mode == 'WB':
                #if a == '0':   # hack!!!! to test the pulse dial
                #    self._rx_buffer.append('\x1bA')   # send text

                # A digit or +/- is being dialled; record digit and trigger dial
                # thread to check
                if a.isdigit() or a == '-' or (self._dial_timeout is None and a == '+'):
                    self._dial_number += a
                    if self._dial_number == '000':
                        self.enable_cli(True)
                        self._dial_number = ''
                        self._dial_change.clear()
                        return True
                    self._dial_change.set()
                else:
                    # Invalid data for dial mode, except it's an error printed by
                    # txDevITelexClient
                    if source == '>':
                        # Error message, print
                        return None
                    else:
                        # Invalid data, discard
                        return True

    # -----

    def idle20Hz(self):
        self._wd.process()

    # =====

    def thread_dial(self):
        # This thread monitors the number-to-dial and initiates the dial
        # command depending on the set mode (instant dialling, timeout dialling
        # or plus dialling)
        #
        # Instant dialling is the classic dial method used in older piTelex
        # versions. It's selected if the configured timeout is 0. In contrast
        # to the other methods, dialling is tried after every entered digit,
        # i.e. incrementally.
        #
        # Timeout dialling behaviour is based on i-Telex r874 (as documented in
        # the comments at trunk/iTelex/iTelex.c:4586) and simplified:
        #
        # 1. After each digit, the local user list is searched in i-Telex.
        #    In piTelex, we don't, because in the current architecture it would
        #    complicate things quite a bit.
        # 2. TNS server is queried if at least five digits have been dialled
        #    and no further digit is dialled for two seconds
        # 3. If there is a positive result from a local or TNS query, try to
        #    establish a connection
        # 4. Dialling is cancelled if a connection attempt in 3. failed or if
        #    nothing further is dialled for 15 seconds
        #
        # Plus dialling simply waits for digits and dials if '+' is entered.
        #
        # The condition "five digits minimum" is fulfilled in
        # txDevITelexClient.

        # change holds the return value of _dial_change.wait: False if returning by
        # timeout, True otherwise
        change = True

        while self._run:
            if (not self._dial_number) or self._mode != 'WB':
                # Number empty or not in dial mode -- wait for next change and
                # recheck afterwards.
                change = self._dial_change.wait()
                self._dial_change.clear()
                continue

            if self._dial_timeout == 0:
                # Instant dialling: Just try dialling on every digit, failing
                # silently if number not found (ESC-#! instead of ESC-#,
                # handled in txDevITelexClient).
                self._rx_buffer.append('\x1b#!' + self._dial_number)
                # NB: We keep self._dial_number here to allow incremental
                # dialling. It is reset not inside this thread like with the
                # other methods, but from the outside (on receipt of ESC-A).
                change = self._dial_change.wait()
                self._dial_change.clear()
                continue

            # Other dialling methods start here.
            while True:
                # There is a number being dialled. This loop runs once for
                # every digit dialled and checks if the dial condition is
                # fulfilled:
                #
                # - '+' dialling: number complete when finished by +
                # - timeout dialling: number complete when timeout occurs
                #
                # On dial, we break out of the loop and queue the dial command,
                # which is executed by txDevMCP. For details see
                # txDevMCP.get_user.

                if change:
                    # A change in self._dial_number has occurred
                    if self._dial_timeout is None:
                        # We are in + dial mode: Check if the last change was a
                        # plus, otherwise ignore
                        if self._dial_number[-1] == '+':
                            # Remove trailing + and dial
                            self._dial_number = self._dial_number[:-1]
                            break
                    else:
                        # We are in timeout dial mode, just save the digit and
                        # continue
                        pass
                else:
                    # No change in dialled number; wait method timed out. This
                    # can only happen in timeout dialling mode and if at least
                    # one digit has been dialled. Dial now.
                    break

                # Before the next iteration, wait on the next change
                change = self._dial_change.wait(self._dial_timeout)
                self._dial_change.clear()

            # We've got a "go" for dialling, either by timeout or by +
            if self._dial_number:
                self._rx_buffer.append('\x1b#' + self._dial_number)
                self._dial_number = ''
            # TODO have dial command always print an error on fail

    # -----

    def _watchdog_callback_ST(self, name:str):
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
            self._wd.disable('WB')
        else:
            self.cli_enable = False

#######

