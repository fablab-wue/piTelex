#!/usr/bin/python3
"""
Telex Device - Serial Communication over System TTY in ASCII-Mode

EPSON is a registered trademark of Seiko Epson Corporation.
ESC/POS is a registered trademark or trademark of Seiko Epson Corporation.
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2021, JK"
__license__     = "GPL3"
__version__     = "0.0.2"

import serial
import serial.rs485
import time

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import log

#######

class TelexTerminal(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'Trm'
        self.params = params

        portname = params.get('portname', '/dev/ttyUSB0')
        baudrate = params.get('baudrate', 300)
        bytesize = params.get('bytesize', 8)
        stopbits = params.get('stopbits', serial.STOPBITS_ONE)
        parity   = params.get('parity', serial.PARITY_NONE)
        dsrdtr   = params.get('dsrdtr', False)
        rtscts   = params.get('rtscts', False)
        xonxoff  = params.get('xonxoff', False)
        RS485  = params.get('RS485', False)
        self._local_echo = params.get('loc_echo', True)
        self._show_capital = self.params.get('show_capital', False)
        self._show_BuZi = self.params.get('show_BuZi', False)
        self._show_ctrl = self.params.get('show_ctrl', True)
        self._show_info = self.params.get('show_info', False)
        self._send_only = self.params.get('send_only', False)
        self._auto_CRLF = self.params.get('auto_CRLF', 0)
        self._replace_char = self.params.get('replace_char', {})
        self._replace_esc = self.params.get('replace_esc', {})

        self._rx_buffer = []

        # init serial
        if RS485:
            self._tty = serial.rs485.RS485(portname, write_timeout=0)
        else:
            self._tty = serial.Serial(portname, write_timeout=0)

        if baudrate not in self._tty.BAUDRATES:
            raise Exception('Baudrate not supported')
        if bytesize not in self._tty.BYTESIZES:
            raise Exception('Databits not supported')
        if stopbits not in self._tty.STOPBITS:
            raise Exception('Stopbits not supported')
        if parity not in self._tty.PARITIES:
            raise Exception('Parity not supported')

        self._tty.baudrate = baudrate
        self._tty.bytesize = bytesize
        self._tty.stopbits = stopbits
        self._tty.parity = parity
        self._tty.dsrdtr = dsrdtr
        self._tty.rtscts = rtscts
        self._tty.xonxoff = xonxoff
        if RS485:
            self._tty.rs485_mode = serial.rs485.RS485Settings()

        text = params.get('init', '')
        if text:
            self._write_hextext(text)
        
        self.char_count = 0

    # -----

    def exit(self):
        self._tty.close()

    # -----

    def __del__(self):
        super().__del__()

    # =====

    def read(self) -> str:
        if self._send_only:
            return
        if self._tty.in_waiting:
            b = self._tty.read(1)
            if b[0] < 0x20:
                pass
            else:
                if self._local_echo:
                    self._write_raw(b)
                a = b.decode('ASCII', errors='ignore')
                if a:
                    a = a.upper()
                    self._rx_buffer.append(a)

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)
            return ret

    # -----

    def write(self, a:str, source:str):
        if not a:
            return

        if len(a) != 1:
            a = a[1:]
            if a in self._replace_esc:
                self._write_hextext(self._replace_esc.get(a, '?'))
                return

            self._check_commands(a)
            if (self._show_ctrl and a[0].isalpha()) or (self._show_info and not a[0].isalpha()):
                a = '{' + a + '}'
            else:
                return

        else:   # single char
            if not self._show_BuZi and a in '<>':
                return
            if a in self._replace_char:
                self._write_hextext(self._replace_char.get(a, '?'))
                return

            if self._show_capital:
                a = a.upper()
            else:
                a = a.lower()
            
        self._write_ascii(a)

    # =====

    def _write_raw(self, bb:bytes):
        self._tty.write(bb)

    # -----

    def _write_ascii(self, text:str):
        if not text:
            return

        bb = text.encode('ASCII')
            
        if self._auto_CRLF:
            for b in bb:
                self.char_count += 1
                if b == b'\r':
                    self.char_count = 0
                self._write_raw(b)
                if self.char_count >= self._auto_CRLF:
                    self._write_raw(b'\r\n')
                    self.char_count = 0

        else:
            self._write_raw(bb)

    # -----

    def _write_hextext(self, s:str):
        if not s:
            return b''

        ishex = False
        hexval = ''
        for c in s:
            if c == '[':   # start hex string
                ishex = True
                hexval = ''
            elif c == ']':   # end hex string
                ishex = False
            else:   # normal char
                if ishex:
                    if c == ' ':
                        continue
                    if hexval == '':
                        hexval = c
                    else:
                        hexval += c
                        self._write_raw(bytes([int(hexval, 16)]))
                        hexval = ''
                else:
                    self._write_ascii(c)

    # =====

    def idle20Hz(self):
        pass

    # -----

    def idle(self):
        pass

    # =====

    def _check_commands(self, a:str):
        if a == 'A':
            pass

        if a == 'Z':
            pass

        if a == 'WB':
            pass

#######
