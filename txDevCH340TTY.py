#!/usr/bin/python3
"""
Telex Device - Serial Communication over CH340-Chip (not FTDI, not Prolific, not CP213x)

Protocol:
https://wiki.telexforum.de/index.php?title=TW39_Verfahren_(Teil_2)

"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "2.1.0"

"""
updated to use with answerbox 2026-04-12 WH
whilst i have NO ch340TTY-telex, it is NOT tested
please report error or success to wolfhenk@wolfhenk.de or telex 38718 wlfhnk d
"""

import serial
import time

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase

#def LOG(text:str, level:int=3):
#    #log.LOG('\033[30;43m<'+text+'>\033[0m', level)

#######

class TelexCH340TTY(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'chT'
        self.params = params

        portname = params.get('portname', '/dev/ttyUSB0')
        baudrate = params.get('baudrate', 50)
        bytesize = params.get('bytesize', 5)
        stopbits = params.get('stopbits', serial.STOPBITS_ONE_POINT_FIVE)
        coding = params.get('coding', 0)
        loopback = params.get('loopback', None)
        inverse_dtr = params.get('inverse_dtr', False)
        self._local_echo = params.get('loc_echo', False)

        self._rx_buffer = []
        self._tx_buffer = []
        self._counter_LTRS = 0
        self._counter_FIGS = 0
        self._counter_dial = 0
        self._time_last_dial = 0
        self._cts_stable = True   # rxd=Low
        self._cts_counter = 0
        self._time_squelch = 0
        self._time_tx_lock = 0
        self._is_enabled = False
        self._is_online = False
        self._last_out_waiting = 0

        self._daytime = True
        self._pending_mode_cmd = None
        self._pending_local_at = False

        self._set_mode(params['mode'])
        if loopback is not None:
            self._loopback = loopback

        self._inverse_dtr = params.get('inverse_dtr', self._inverse_dtr)
        self._inverse_rts = params.get('inverse_rts', self._inverse_rts)

        # init serial
        self._tty = serial.Serial(portname, write_timeout=0)

        if baudrate not in self._tty.BAUDRATES and baudrate not in (45, 100):
            raise Exception('Baudrate not supported')
        if bytesize not in self._tty.BYTESIZES:
            raise Exception('Databits not supported')
        if stopbits not in self._tty.STOPBITS:
            raise Exception('Stopbits not supported')

        self._tty.baudrate = baudrate
        self._tty.bytesize = bytesize
        self._tty.stopbits = stopbits
        self._baudrate = baudrate
        self._inverse_dtr = inverse_dtr

        # init codec
        #character_duration = (bytesize + 1.0 + stopbits) / baudrate
        character_duration = (bytesize + 3.0 ) / baudrate   # CH340 sends always with 2 stop bits
        self._mc = txCode.BaudotMurrayCode(self._loopback, coding=coding, character_duration=character_duration)

        self._set_enable(False)
        self._set_online(False)

    # -----

    def _set_mode(self, mode:str):
        self._loopback = False
        self._use_pulse_dial = False
        self._use_squelch = False
        self._use_cts = False
        self._inverse_cts = False
        #self._use_dtr = False
        self._inverse_dtr = False
        self._inverse_rts = False
        self._use_dedicated_line = True

        mode = mode.upper()

        if mode.find('TW39') >= 0:
            self._loopback = True
            self._use_cts = True
            self._use_pulse_dial = True
            self._use_squelch = True
            self._use_dedicated_line = False

        if mode.find('TWM') >= 0:
            self._loopback = True
            self._use_cts = True
            self._use_pulse_dial = False
            self._use_squelch = True
            self._use_dedicated_line = False

        if mode.find('V.10') >= 0 or mode.find('V10') >= 0:
            self._use_cts = True
            self._inverse_cts = True
            #self._inverse_dtr = True
            self._use_dedicated_line = False

        if mode.find('EDS') >= 0:
            self._loopback = False
            self._use_cts = True
            self._inverse_dtr = True
            self._use_squelch = True
            self._use_dedicated_line = False


    # -----

    def exit(self):
        self._tty.close()

    # -----

    def __del__(self):
        super().__del__()

    # =====

    def read(self) -> str:
        if self._tty.in_waiting:
            a = ''

            bb = self._tty.read(1)

            if bb and (not self._use_squelch or time.monotonic() >= self._time_squelch):
                if self._daytime:
                    if self._is_enabled or self._use_dedicated_line:
                        if self._local_echo:
                            self._tty.write(bb)

                        a = self._mc.decodeBM2A(bb)

                        if a:
                            self._check_special_sequences(a)

                    elif self._is_online and self._use_pulse_dial:
                        b = bb[0]

                        if b == 0:   # break or idle mode
                            pass
                        elif (b & 0x13) == 0x10:   # valid dial pulse - min 3 bits = 40ms, max 5 bits = 66ms
                            self._counter_dial += 1
                            self._time_last_dial = time.monotonic()

                elif (self._is_enabled or self._use_dedicated_line) and not self._use_cts:
                    a = self._mc.decodeBM2A(bb)

                    if a:
                        self._check_special_sequences(a)

                self._cts_counter = 0

                if a and self._daytime:
                    self._rx_buffer.append(a)
                    #if self._local_echo:
                    #    self._tx_buffer.append(a)

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)
            return ret

    # -----

    def write(self, a:str, source:str):
        if len(a) > 1 and a[0] == '\x1b':
            a = a[1:]
            if a == 'DTM' or a == 'NTM':
                self._pending_mode_cmd = a
                return

            if not self._daytime:
                return

            self._check_commands(a)
            return

        if not self._daytime:
            return

        if a == '#':
            a = '@'   # ask teletype for hardware ID

        if a:
            if self._is_enabled or self._use_dedicated_line:
                self._tx_buffer.append(a)

    # =====

    def idle(self):
        if self._pending_mode_cmd:
            a = self._pending_mode_cmd
            self._pending_mode_cmd = None
            self._check_commands(a)
            return

        if not self._daytime:
            return

        if (not self._use_squelch) or time.monotonic() >= max(self._time_squelch, self._time_tx_lock):
            if self._tx_buffer:
                aa = []
                a = None
                while a != '@' and self._tx_buffer:
                    a = self._tx_buffer.pop(0)
                    aa.append(a)
                    if a == '@':
                        # WRU received: lock sending until after 21 character's
                        # time has passed. This may need to be raised due to
                        # the CH340's substantial write buffer.
                        self._time_tx_lock = time.monotonic() + 7.5*21/self._baudrate

                aa = ''.join(aa)
                self._tx_buffer = []
                bb = self._mc.encodeA2BM(aa)
                if bb:
                    self._rx_buffer.append('\x1b~' + str(self._tty.out_waiting + len(bb)))
                    # Force-update last out_waiting value to trigger idle2Hz update
                    self._last_out_waiting += len(bb)
                    self._tty.write(bb)

    # -----

    def idle20Hz(self):
        time_act = time.monotonic()

        if self._daytime and self._use_pulse_dial and self._counter_dial and (time_act - self._time_last_dial) > 0.2:
            if self._counter_dial >= 10:
                self._counter_dial = 0
            a = str(self._counter_dial)
            self._rx_buffer.append(a)
            self._time_last_dial = time_act
            self._counter_dial = 0

        if self._use_cts:
            cts = not self._tty.cts != self._inverse_cts   # logical xor
            if cts != self._cts_stable:
                self._cts_counter += 1
                if self._cts_counter == 10:   # 0.5sec
                    self._cts_stable = cts
                    if not cts:   # rxd=Low
                        if self._daytime:
                            self._rx_buffer.append('\x1bST')
                        pass
                    elif not self._is_enabled:   # rxd=High
                        if self._daytime:
                            self._rx_buffer.append('\x1bAT')
                        elif not self._pending_local_at:
                            self._pending_local_at = True
                            self._rx_buffer.append('\x1bWUP')
                        pass
                    pass
            else:
                self._cts_counter = 0

    # -----

    def idle2Hz(self):
        if not self._daytime:
            return

        # send printer FIFO info
        out_waiting = self._tty.out_waiting
        if out_waiting != self._last_out_waiting:
            self._rx_buffer.append('\x1b~' + str(out_waiting))
            self._last_out_waiting = out_waiting

    # -----

    def _set_online(self, online:bool):
        self._is_online = online
        self._tty.rts = online != self._inverse_rts    # RTS

    # -----

    def _set_enable(self, enable:bool):
        self._is_enabled = enable
        self._tty.dtr = enable != self._inverse_dtr    # DTR -> True=Low=motor_on
        if 0:   # experimental
            self._tty.break_condition = not enable
        self._mc.reset()
        if self._use_squelch:
            self._set_time_squelch(0.5)
        #self._tty.send_break(1.0)

    # -----

    def _set_time_squelch(self, t_diff):
        t = time.monotonic() + t_diff
        if self._time_squelch < t:
            self._time_squelch = t

    # -----

    def _set_pulse_dial(self, enable:bool):
        if not self._use_pulse_dial:
            return

        if enable:
            self._tty.baudrate = 75   # fix baudrate to scan number switch
        else:
            self._tty.baudrate = self._baudrate

    # =====

    def _check_special_sequences(self, a:str):
        if not self._use_cts:
            if a == '<':
                self._counter_LTRS += 1
                if self._counter_LTRS == 5 and self._daytime:
                    self._rx_buffer.append('\x1bST')
            else:
                self._counter_LTRS = 0

            if a == '>':
                self._counter_FIGS += 1
                if self._counter_FIGS == 5:
                    if self._daytime:
                        self._rx_buffer.append('\x1bAT')
                    elif not self._pending_local_at:
                        self._pending_local_at = True
                        self._rx_buffer.append('\x1bWUP')
            else:
                self._counter_FIGS = 0

    # -----

    def _check_commands(self, a:str):
        enable = None

        if a == 'DTM':
            self._daytime = True
            if self._pending_local_at:
                self._pending_local_at = False
                self._rx_buffer.append('\x1bAT')
            return

        elif a == 'NTM':
            self._daytime = False
            self._pending_local_at = False
            self._tx_buffer = []
            self._rx_buffer = []
            return

        if not self._daytime:
            return

        if a in ('A',):
            # Confirm enable status for MCP
            self._rx_buffer.append('\x1bAA')

        if a in ('A', 'AA'):
            self._set_pulse_dial(False)
            self._set_online(True)
            enable = True

        if a in ('Z', 'ZZ'):
            self._tx_buffer = []    # empty write buffer...
            self._set_pulse_dial(False)
            self._set_online(False)
            enable = False   #self._use_dedicated_line
            if not enable and self._use_squelch:
                self._set_time_squelch(1.5)

        if a in ('WB',):
            self._set_online(True)
            if self._use_pulse_dial:   # TW39
                self._set_pulse_dial(True)
                self._tty.write(b'\x1E')   # send pulse with 25ms low to signal 'ready for dialing' ('Wahlbereitschaft')
                enable = False
            else:   # dedicated line, TWM, V.10
                enable = True

        if enable is not None:
            self._set_enable(enable)

#######
