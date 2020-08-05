#!/usr/bin/python3
"""
Telex Device - i-Telex Common Routines in Client and Server
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread
import socket
import time
import datetime
import sys
import random
random.seed()

import logging
l = logging.getLogger("piTelex." + __name__)
#l.setLevel(logging.DEBUG)

import txCode
import txBase

# i-Telex allowed package types for Baudot texting mode
# (everything else triggers ASCII texting mode)
from itertools import chain
allowed_types = lambda: chain(range(0x00, 0x09+1), range(0x10, 0x1f+1))

#######

# Decoding and encoding of extension numbers (see i-Telex specification, r874)
#
#            encoded         decoded
# (raw network data)    (as dialled)
#
#                  0            none
#                  1              01
#                  2              02
#                ...             ...
#                 99              99
#                100              00
#                101               1
#                102               2
#                ...
#                109               9
#                110               0
#               >110         invalid

def decode_ext_from_direct_dial(ext:int) -> str:
    """
    Decode integer extension from direct dial packet and return as str.
    """
    ext = int(ext)
    if ext == 0:
        return None
    elif 1 <= ext <= 100:
        # Two-digit extension (leading zero if applicable)
        return "{:02d}".format(ext%100)
    elif 101 <= ext <= 110:
        # single-digit extension
        return str(ext%10)
    else:
        # invalid!
        l.warning("Invalid direct dial extension: {} (falling back to 0)".format(ext))
        return None

def encode_ext_for_direct_dial(ext:str) -> int:
    """
    Encode str extension to integer extension for direct dial packet and return
    it.
    """
    if not ext:
        # no extension
        return 0
    try:
        ext_int = int(ext)
    except (ValueError, TypeError):
        l.warning("Invalid direct dial extension: {!r} (falling back to none)".format(ext))
        return 0
    if len(ext) == 1:
        return 110 if not ext_int else ext_int + 100
    elif len(ext) == 2:
        return 100 if not ext_int else ext_int
    else:
        l.warning("Invalid direct dial extension: {!r} (falling back to none)".format(ext))
        return 0


def display_hex(data:bytes) -> str:
    """
    Convert a byte string into a string of hex values for diplay.
    """
    return " ".join(hex(i) for i in data)


class TelexITelexCommon(txBase.TelexBase):
    def __init__(self):
        super().__init__()

        self._rx_buffer = []
        self._tx_buffer = []
        self._connected = 0
        self._run = True


    def __del__(self):
        self.exit()
        super().__del__()


    def exit(self):
        self._run = False
        self._connected = 0

    # =====

    def disconnect_client(self):
        self._tx_buffer = []
        self._connected = 0

    # =====

    def process_connection(self, s:socket.socket, is_server:bool, is_ascii:bool):  # Takes client socket as argument.
        """Handles a client or server connection."""
        bmc = txCode.BaudotMurrayCode(False, False, True)
        sent_counter = 0
        received_counter = 0
        timeout_counter = -1
        time_next_send = None
        error = False

        s.settimeout(0.2)

        # Connection states:
        # 0: disconnected
        # 1: connected, but printer not yet started
        # 2: connected, printer has been started, welcome banner hasn't been
        #    fully received yet
        # 3: connected, welcome banner has been received completely
        self._connected = 1

        # Store remote protocol version to control negotiation
        self._remote_protocol_ver = None

        # Connection type hinting and detection
        if is_ascii is None:
            l.info('Connection hint: auto-detect enabled')
        elif is_ascii:
            l.info('Connection hint: ASCII connection')
        else:
            l.info('Connection hint: i-Telex connection')

        # The rationale here is to, after starting the printer, first print the
        # complete welcome banner. Received data must only by printed *after*
        # this.
        #
        # The typical sequence is as follows:
        #
        # - After printable data is received for the first time, we decide on
        #   the connection type (Baudot or ASCII), queue some commands (start
        #   printer, MCP output welcome banner) and also queue the received
        #   data afterwards. (state 2)
        #
        # - Main loop read()-s us. Our read method is filtered (based on state
        #   2) so that only commands are read, printable data is retained for
        #   later perusal.
        #
        # - Eventually, MCP receives the welcome banner command. It sends the
        #   banner, which is writ[e]()-ten to us. After the banner, it sends
        #   the ESC-WELCOME command which tells us the banner has been written
        #   completely. On this command, our read method is unlocked and
        #   previously received data is available for main loop. (state 3)

        # Start with 0 to trigger log message
        _connected_before = 0
        while self._connected > 0:
            if _connected_before != self._connected:
                l.info("State transition: {}=>{}".format(_connected_before, self._connected))
                _connected_before = self._connected
            try:
                data = s.recv(1)

                # piTelex terminates; close connection
                if not self._run:
                    break

                # lost connection
                if not data:
                    l.warning("Remote has closed connection")
                    break

                # Telnet control sequence
                elif data[0] == 255:
                    d = s.recv(2)   # skip next 2 bytes from telnet command

                # i-Telex packet
                elif data[0] in allowed_types():
                    packet_error = False

                    d = s.recv(1)
                    data += d
                    packet_len = d[0]
                    if packet_len:
                        data += s.recv(packet_len)

                    # Heartbeat
                    if data[0] == 0 and packet_len == 0:
                        l.debug('Received i-Telex packet: Heartbeat ({})'.format(display_hex(data)))

                    # Direct Dial
                    elif data[0] == 1 and packet_len == 1:
                        l.debug('Received i-Telex packet: Direct dial ({})'.format(display_hex(data)))

                        # Disable emitting "direct dial" command, since it's
                        # currently not acted upon anywhere.
                        #self._rx_buffer.append('\x1bD'+str(data[2]))

                        # Instead, only accept extension 0 (i-Telex default)
                        # and None, and reject all others.
                        ext = decode_ext_from_direct_dial(data[2])
                        l.info('Direct Dial, extension {}'.format(ext))
                        if not ext in ('0', None):
                            self.send_reject(s, 'na')
                            error = True
                            break
                        else:
                            # TODO: Start up printer properly and fail if it
                            # doesn't work.
                            if 0 < self._connected < 2:
                                # Start printer and send welcome banner
                                self._rx_buffer.append('\x1bA')
                                self._connected = 2
                                if is_server:
                                    self._tx_buffer = []
                                    self.send_welcome(s)
                            self.send_ack(s, received_counter)

                    # Baudot Data
                    elif data[0] == 2 and packet_len >= 1 and packet_len <= 50:
                        l.debug('Received i-Telex packet: Baudot data ({})'.format(display_hex(data)))
                        aa = bmc.decodeBM2A(data[2:])
                        # TODO: Start up printer properly and fail if it
                        # doesn't work.
                        if 0 < self._connected < 2:
                            # Start printer and send welcome banner
                            self._rx_buffer.append('\x1bA')
                            self._connected = 2
                            if is_server:
                                self._tx_buffer = []
                                self.send_welcome(s)
                        for a in aa:
                            if a == '@':
                                a = '#'
                            self._rx_buffer.append(a)
                        received_counter += len(data[2:])
                        self.send_ack(s, received_counter)

                    # End
                    elif data[0] == 3 and packet_len == 0:
                        l.debug('Received i-Telex packet: End ({})'.format(display_hex(data)))
                        l.info('End by remote')
                        break

                    # Reject
                    elif data[0] == 4 and packet_len <= 20:
                        l.debug('Received i-Telex packet: Reject ({})'.format(display_hex(data)))
                        aa = bmc.translate(data[2:])
                        l.info('i-Telex connection rejected, reason {!r}'.format(aa))
                        for a in aa:
                            self._rx_buffer.append(a)
                        break

                    # Acknowledge
                    elif data[0] == 6 and packet_len == 1:
                        l.debug('Received i-Telex packet: Acknowledge ({})'.format(display_hex(data)))
                        # TODO: Fix calculation and prevent overflows, e.g. if
                        # the first ACK is sent with a low positive value. This
                        # might be done by saving the first ACK's absolute
                        # counter value and only doing difference calculations
                        # afterwards.
                        unprinted = (sent_counter - int(data[2])) & 0xFF
                        #if unprinted < 0:
                        #    unprinted += 256
                        l.debug(str(data[2])+'/'+str(sent_counter)+'='+str(unprinted) + " (printed/sent=unprinted)")
                        if unprinted < 7:   # about 1 sec
                            time_next_send = None
                        else:
                            time_next_send = time.time() + (unprinted-6)*0.15
                        pass

                    # Version
                    elif data[0] == 7 and packet_len >= 1 and packet_len <= 20:
                        l.debug('Received i-Telex packet: Version ({})'.format(display_hex(data)))
                        if self._remote_protocol_ver is None:
                            if data[2] != 1:
                                # This is the first time an unsupported version was offered
                                l.warning("Unsupported version offered by remote ({}), requesting v1".format(display_hex(data[2:])))
                                self.send_version(s)
                            else:
                                # Only send version packet in response to valid
                                # version when we're server, because as client,
                                # we sent a version packet directly after
                                # connecting.
                                if is_server:
                                    self.send_version(s)
                            # Store offered version
                            self._remote_protocol_ver = data[2]
                        else:
                            if data[2] != 1:
                                # The remote station insists on incompatible
                                # version. Send the not-officially-defined
                                # error code "ver".
                                l.error("Unsupported version insisted on by remote ({})".format(display_hex(data[2:])))
                                self.send_reject(s, 'ver')
                                error = True
                                break
                            else:
                                if data[2] != self._remote_protocol_ver:
                                    l.info("Negotiated protocol version {}, initial request was {}".format(data[2], self._remote_protocol_ver))
                                    self._remote_protocol_ver = data[2]
                                else:
                                    # Ignore multiple good version packets
                                    l.info("Redundant Version packet")

                    # Self test
                    elif data[0] == 8 and packet_len >= 2:
                        l.debug('Received i-Telex packet: Self test ({})'.format(display_hex(data)))

                    # Remote config
                    elif data[0] == 9 and packet_len >= 3:
                        l.info('Received i-Telex packet: Remote config ({})'.format(display_hex(data)))

                    # Wrong packet - will resync at next socket.timeout
                    else:
                        l.warning('Received invalid i-Telex Packet: {}'.format(display_hex(data)))
                        packet_error = True

                    if not packet_error:
                        if is_ascii is None:
                            l.info('Detected i-Telex connection')
                            is_ascii = False
                        elif is_ascii:
                            l.warning('Detected i-Telex connection, but ASCII was expected')
                            is_ascii = False


                # ASCII character(s)
                else:
                    l.debug('Received non-i-Telex data: {} ({})'.format(repr(data), display_hex(data)))
                    if is_ascii is None:
                        l.info('Detected ASCII connection')
                        is_ascii = True
                    elif not is_ascii:
                        l.warning('Detected ASCII connection, but i-Telex was expected')
                        is_ascii = True
                    # TODO: Start up printer properly and fail if it
                    # doesn't work.
                    if 0 < self._connected < 2:
                        # Start printer and send welcome banner
                        self._rx_buffer.append('\x1bA')
                        self._connected = 2
                        if is_server:
                            self._tx_buffer = []
                            self.send_welcome(s)
                    data = data.decode('ASCII', errors='ignore').upper()
                    data = txCode.BaudotMurrayCode.translate(data)
                    for a in data:
                        if a == '@':
                            a = '#'
                        self._rx_buffer.append(a)
                        received_counter += 1

            except socket.timeout:
                #l.debug('.')
                if is_server and self.printer_start_timed_out:
                    self.printer_start_timed_out = False
                    if is_ascii:
                        s.sendall(b"der")
                    else:
                        self.send_reject(s, "der")
                    l.error("Disconnecting client because printer didn't start up")
                    error = True
                    break
                if is_ascii is not None:   # either ASCII or baudot connection detected
                    timeout_counter += 1

                    if is_ascii:
                        if self._tx_buffer:
                            sent = self.send_data_ascii(s)
                            sent_counter += sent

                    else:   # baudot
                        if (timeout_counter % 5) == 0:   # every 1 sec
                            self.send_ack(s, received_counter)

                        if self._tx_buffer:
                            if time_next_send and time.time() < time_next_send:
                                l.debug('Sending paused for {:.3f} s'.format(time_next_send-time.time()))
                                pass
                            else:
                                sent = self.send_data_baudot(s, bmc)
                                sent_counter += sent
                                if sent > 7:
                                    time_next_send = time.time() + (sent-6)*0.15

                        elif (timeout_counter % 15) == 0:   # every 3 sec
                            self.send_heartbeat(s)


            except socket.error:
                l.error("Exception caught:", exc_info = sys.exc_info())
                error = True
                break


        if not is_ascii:
            # Don't send end packet in case of error. There may be two error
            # cases:
            # - Protocol error: We've already sent a reject package.
            # - Network error: There's no connection to send over anymore.
            if not error:
                self.send_end(s)
        l.info('end connection')
        self._connected = 0
        if _connected_before != self._connected:
            l.info("State transition: {}=>{}".format(_connected_before, self._connected))


    def send_heartbeat(self, s):
        '''Send heartbeat packet (0)'''
        data = bytearray([0, 0])
        l.debug('Sending i-Telex packet: Heartbeat ({})'.format(display_hex(data)))
        s.sendall(data)


    def send_ack(self, s, received:int):
        '''Send acknowledge packet (6)'''
        data = bytearray([6, 1, received & 0xff])
        l.debug('Sending i-Telex packet: Acknowledge ({})'.format(display_hex(data)))
        s.sendall(data)


    def send_version(self, s):
        '''Send version packet (7)'''
        send = bytearray([7, 1, 1])
        l.debug('Sending i-Telex packet: Version ({})'.format(display_hex(send)))
        s.sendall(send)


    def send_direct_dial(self, s, dial:str):
        '''Send direct dial packet (1)'''
        l.info("Sending direct dial: {!r}".format(dial))
        data = bytearray([1, 1])   # Direct Dial
        ext = encode_ext_for_direct_dial(dial)
        data.append(ext)
        l.debug('Sending i-Telex packet: Direct dial ({})'.format(display_hex(data)))
        s.sendall(data)


    def send_data_ascii(self, s):
        '''Send ASCII data direct'''
        a = ''
        while self._tx_buffer and len(a) < 250:
            b = self._tx_buffer.pop(0)
            if b not in '<>~%':
                a += b
        data = a.encode('ASCII')
        l.debug('Sending non-i-Telex data: {} ({})'.format(repr(data), display_hex(data)))
        s.sendall(data)
        return len(data)


    def send_data_baudot(self, s, bmc):
        '''Send baudot data packet (2)'''
        data = bytearray([2, 0])
        while self._tx_buffer and len(data) < 42:
            a = self._tx_buffer.pop(0)
            bb = bmc.encodeA2BM(a)
            if bb:
                for b in bb:
                    data.append(b)
        length = len(data) - 2
        data[1] = length
        l.debug('Sending i-Telex packet: Baudot data ({})'.format(display_hex(data)))
        s.sendall(data)
        return length


    def send_end(self, s):
        '''Send end packet (3)'''
        send = bytearray([3, 0])   # End
        l.debug('Sending i-Telex packet: End ({})'.format(display_hex(send)))
        s.sendall(send)


    # Types of reject packets (see txDevMCP):
    #
    # - abs   line disabled
    # - occ   line occupied
    # - der   derailed: line connected, but called teleprinter not starting
    #         up
    # - na    called extension not allowed
    def send_reject(self, s, msg = "abs"):
        '''Send reject packet (4)'''
        send = bytearray([4, len(msg)])   # Reject
        send.extend([ord(i) for i in msg])
        l.debug('Sending i-Telex packet: Reject ({})'.format(display_hex(send)))
        l.info('Reject, reason {!r}'.format(msg))
        s.sendall(send)


    def send_welcome(self, s):
        '''Send welcome message indirect as a server'''
        #self._tx_buffer.extend(list('<<<\r\n'))   # send text
        #self._rx_buffer.append('\x1bT')
        #self._rx_buffer.append('#')
        #self._rx_buffer.append('@')
        self._rx_buffer.append('\x1bI')
        return 24 # fixed length of welcome banner, see txDevMCP

    # i-Telex epoch has been defined as 1900-01-00 00:00:00 (sic)
    # What's probably meant is          1900-01-01 00:00:00
    # Even more probable is UTC, because naive evaluation during a trial gave a 2 h
    # offset during CEST. If needed, this must be expanded for local timezone
    # evaluation.
    itx_epoch = datetime.datetime(
        year = 1900,
        month = 1,
        day = 1,
        hour = 0,
        minute = 0,
        second = 0
    )

    # List of TNS addresses as of 2020-04-21
    # <https://telexforum.de/viewtopic.php?f=6&t=2504&p=17795#p17795>
    _tns_addresses = [
        "sonnibs.no-ip.org",
        "tlnserv.teleprinter.net",
        "tlnserv3.teleprinter.net",
        "telexgateway.de"
    ]

    @classmethod
    def choose_tns_address(cls):
        """
        Return randomly chosen TNS (Telex number server) address, for load
        distribution.
        """
        return random.choice(cls._tns_addresses)


#######

