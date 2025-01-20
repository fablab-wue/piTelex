#!/usr/bin/python3
"""
Telex Device - i-Telex Common Routines in Client and Server
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Lock
import socket
import time
import datetime
import sys
import random
random.seed()
import enum

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


class ST(enum.IntEnum):
    """
    Represent i-Telex connection state.
    """
    # Disconnected, wait for teleprinter to finish printing
    DISCON_TP_WAIT = 1

    # Disconnected
    DISCON = 2

    # Connected, but printer not yet started
    CON_INIT = 3

    # Connected, printer start requested
    CON_TP_REQ = 4

    # Connected, printer has been started:
    # - client: good to go (state will be advanced w/o condition)
    # - server: waiting for welcome banner, we'll withhold other data in read
    #   method
    CON_TP_RUN = 5

    # Connected, good to go
    CON_FULL = 6

class TelexITelexCommon(txBase.TelexBase):
    def __init__(self):
        super().__init__()

        # Warning! _rx_buffer is modified simultaneously by two threads when
        # operating as server. For this reason, the _rx_lock MUST be acquired
        # while accessing it, or calculating anything depending on it.
        # Otherwise, bad stuff™ will ensue! Use "with" to prevent deadlocks.
        self._rx_buffer = []
        self._rx_lock = Lock()
        self._tx_buffer = []
        self._connected = ST.DISCON
        self._run = True

        # Printer start feedback is saved here
        self._printer_running = False

        # Current length of printer buffer contents
        self._print_buf_len = 0

        self._received_counter = 0
        self._acknowledge_counter = 0
        self._last_acknowledge_counter = 0
        self._send_acknowledge_idle = False

    def __del__(self):
        self.exit()
        super().__del__()


    def exit(self):
        self._run = False
        self._connected = ST.DISCON

    # =====

    def write(self, a:str, source:str):
        # Important: This method must be called from subclasses.
        if a == "\x1bZ":
            self._printer_running = False
            # This is only half of the truth: We do reset printer_running
            # whenever we receive ESC-Z. Often times however, we're the
            # originator of ESC-Z, and this will not be re-writ[t]e()n to us,
            # which is why we need to explicitly set it to False when the
            # connection is terminated (typically inside the derived class's
            # connection handling thread).
        elif a == "\x1bAA": # Printer started
            # In case we're not connected when the printer starts (e.g. for
            # keyboard dial), save started state.
            self._printer_running = True

            if self._connected == ST.CON_TP_REQ:
                # Printer has been started successfully; advance connection
                # state; welcome banner will be sent in process_connection if
                # we're server
                self._connected = ST.CON_TP_RUN

        elif a.startswith("\x1b~"): # Printer buffer feedback
            if self._connected >= ST.CON_FULL or self._connected <= ST.DISCON_TP_WAIT:
                # Evaluate only:
                # - if welcome banner has been sent, if applicable, to minimise
                #   chances to prematurely increment the Acknowledge counter or
                # - if we've disconnected and are waiting for the printer to
                #   finish printing.
                try:
                    print_buf_len = int(a[2:])
                except ValueError:
                    l.warning("Invalid printer buffer length feedback received: {!r}".format(a))
                else:
                    self._print_buf_len = print_buf_len
                    if self._connected >= ST.CON_FULL:
                        self.update_acknowledge_counter(print_buf_len)
                    else: # ST.DISCON_TP_WAIT
                        if not print_buf_len:
                            _connected_before = self._connected
                            self._connected = ST.DISCON
                            l.info("State transition: {!s}=>{!s}".format(_connected_before, self._connected))


    def disconnect_client(self):
        if self._tx_buffer:
            l.warning("While disconnecting, transmit buffer not empty, discarded; contents were: {!r}".format(self._tx_buffer))
        self._tx_buffer = []
        # Set to fully disconnected only if printer buffer is empty. Otherwise,
        # ST.DISCON will be set in write method upon receipt of ESC-~0.
        self._connected = ST.DISCON_TP_WAIT if self._print_buf_len else ST.DISCON


    def idle2Hz(self):
        # Important: This method must be called from subclasses.

        # Send Acknowledge if fully connected (only set flag because we're out
        # of context)
        if self._connected >= ST.CON_FULL:
            self._send_acknowledge_idle = True

    # =====

    def update_acknowledge_counter(self, print_buf_len):
        """
        Update i-Telex Acknowledge counter, which communicates the number of
        printed characters. The following needs to be taken into account:

        - self._received_counter: number of received characters from peer
        - print_buf_len: number of characters currently in teleprinter buffer
        - rx_buffer_unread: number of printable characters still waiting our rx queue

        The number of printed characters equals the received characters minus
        all characters "on the way", i.e. residing in any buffer.
        """
        with self._rx_lock:
            rx_buffer_unread = len([i for i in self._rx_buffer if not i.startswith("\x1b")])
            self._acknowledge_counter = self._received_counter - print_buf_len - rx_buffer_unread
            if self._acknowledge_counter < self._last_acknowledge_counter:
                # New count is smaller than before: reset it to the old value to
                # keep counter monotonically increasing
                l.info("Acknowledge counter calculated as {}, reset to {}".format(self._acknowledge_counter, self._last_acknowledge_counter))
                l.info("{}(received_counter) - {}(print_buf_len) - {}(rx_buffer_unread) = {}(acknowledge_counter)".format(self._received_counter, print_buf_len, rx_buffer_unread, self._acknowledge_counter))
                l.info("rx_buffer contents: {!r}".format(self._rx_buffer))
                self._acknowledge_counter = self._last_acknowledge_counter
            else:
                l.debug("{}(received_counter) - {}(print_buf_len) - {}(rx_buffer_unread) = {}(acknowledge_counter)".format(self._received_counter, print_buf_len, rx_buffer_unread, self._acknowledge_counter))
                self._last_acknowledge_counter = self._acknowledge_counter


    def process_connection(self, s:socket.socket, is_server:bool, is_ascii:bool):  # Takes client socket as argument.
        """Handles a client or server connection."""

        # print("process_connection")

        bmc = txCode.BaudotMurrayCode(False, False, True)
        sent_counter = 0
        self._received_counter = 0
        timeout_counter = -1
        time_next_send = None
        error = False

        s.settimeout(0.2)

        self._connected = ST.CON_INIT

        # Store remote protocol version to control negotiation
        self._remote_protocol_ver = None

        # Connection type hinting and detection
        if is_ascii is None:
            l.info('Connection hint: auto-detect enabled')
        elif is_ascii:
            l.info('Connection hint: ASCII connection')
        else:
            l.info('Connection hint: i-Telex connection')

        # New printer feedback based on ESC-~
        #
        # Overview:
        # - i-Telex requires us to periodically send Acknowledge packets so
        #   that the sending party can determine how much of the sent data has
        #   been printed already. Its payload is an 8 bit monotonic counter of
        #   undefined reference point. It should however be 0 as soon as we're
        #   ready to receive and print data.
        #
        # - Basic function: We count data received from remote and subtract
        #   current printer buffer contents. Special care is taken to keep the
        #   counter monotonically increasing, which otherwise might happen if
        #   other modules than us also send data to the printer.

        # If we're server, use negative Acknowledge counter first to allow for
        # fixed-length welcome banner printing
        self._acknowledge_counter = self._last_acknowledge_counter = (-24 if is_server else 0) # fixed length of welcome banner, see txDevMCP

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
        #   previously received data is available for main loop. (state 4)

        # Start with ST.DISCON to trigger log message
        _connected_before = ST.DISCON
        while self._connected > ST.DISCON:
            if _connected_before != self._connected:
                l.info("State transition: {!s}=>{!s}".format(_connected_before, self._connected))
                _connected_before = self._connected
                # For outgoing ASCII connections, connect immediately to be
                # able trigger "lazy" services from the teleprinter
                if self._connected == ST.CON_INIT and is_ascii and not is_server:
                    if not self._printer_running:
                        # Request printer start; confirmation will
                        # arrive as ESC-~ (write method will
                        # advance to ST.CON_TP_RUN and do what's in
                        # the following else block)
                        self._connected = ST.CON_TP_REQ
                        self._rx_buffer.append('\x1bA')
                    else:
                        # Printer already running; welcome banner
                        # will be sent above in next iteration if
                        # we're server
                        self._connected = ST.CON_TP_RUN
                        self._rx_buffer.append('\x1bA')
                    continue
                # We just entered ST.CON_TP_RUN (printer running, waiting for
                # welcome banner)
                elif self._connected == ST.CON_TP_RUN:
                    if is_server:
                        # Send welcome banner
                        self._tx_buffer = []
                        self.send_welcome(s)
                    else:
                        # We're client: skip ST.CON_TP_RUN
                        self._connected = ST.CON_FULL
                        continue
                elif self._connected == ST.CON_FULL:
                    # Send first Acknowledge
                    if not is_ascii:
                        # Send fixed value in Acknowledge packet, mainly for
                        # server case (24 characters of welcome banner have to
                        # be printed before anything else). Typically, the
                        # welcome banner hasn't yet reached the printer buffer,
                        # which would lead to sending 0 instead of -24.
                        #
                        # The next timed Acknowledge will be sent with a filled
                        # printer buffer in most cases. If not, the damage
                        # should be manageable.
                        #
                        # (This problem results from the non-deterministic
                        # sequence with the current piTelex architecture,
                        # namely multiple threads and message passing in a
                        # central loop, and can be solved best by a major
                        # restructuring.)
                        self.send_ack(s, (-24 if is_server else 0)) # fixed length of welcome banner, see txDevMCP

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
                        #with self._rx_lock:
                        #    self._rx_buffer.append('\x1bD'+str(data[2]))

                        # Instead, only accept extension 0 (i-Telex default)
                        # and None, and reject all others.
                        ext = decode_ext_from_direct_dial(data[2])
                        l.info('Direct Dial, extension {}'.format(ext))
                        if not ext in ('0', None):
                            self.send_reject(s, 'na')
                            error = True
                            break
                        else:
                            if self._connected == ST.CON_INIT:
                                if not self._printer_running:
                                    # Request printer start; confirmation will
                                    # arrive as ESC-~ (write method will
                                    # advance to ST.CON_TP_RUN and do what's in
                                    # the following else block)
                                    self._connected = ST.CON_TP_REQ
                                    with self._rx_lock: self._rx_buffer.append('\x1bA')
                                else:
                                    # Printer already running; welcome banner
                                    # will be sent above in next iteration if
                                    # we're server
                                    self._connected = ST.CON_TP_RUN
                                    with self._rx_lock: self._rx_buffer.append('\x1bA')

                    # Baudot Data
                    elif data[0] == 2 and packet_len >= 1 and packet_len <= 50:
                        l.debug('Received i-Telex packet: Baudot data ({})'.format(display_hex(data)))
                        aa = bmc.decodeBM2A(data[2:])
                        if self._connected == ST.CON_INIT:
                            if not self._printer_running:
                                # Request printer start; confirmation will
                                # arrive as ESC-~ (write method will
                                # advance to ST.CON_TP_RUN and do what's in
                                # the following else block)
                                self._connected = ST.CON_TP_REQ
                                with self._rx_lock: self._rx_buffer.append('\x1bA')
                            else:
                                # Printer already running; welcome banner
                                # will be sent above in next iteration if
                                # we're server
                                self._connected = ST.CON_TP_RUN
                                with self._rx_lock: self._rx_buffer.append('\x1bA')
                        with self._rx_lock:
                            for a in aa:
                                if a == '@':
                                    a = '#'
                                self._rx_buffer.append(a)
                        self._received_counter += len(data[2:])
                        # Send Acknowledge if printer is running and we've got
                        # at least 16 characters left to print
                        if self._connected >= ST.CON_FULL and self._print_buf_len >= 16:
                            self.send_ack(s, self._acknowledge_counter)

                    # End
                    elif data[0] == 3 and packet_len == 0:
                        l.debug('Received i-Telex packet: End ({})'.format(display_hex(data)))
                        l.info('End by remote')
                        break

                    # Reject
                    elif data[0] == 4 and packet_len <= 20:
                        l.debug('Received i-Telex packet: Reject ({})'.format(display_hex(data)))
                        aa = data[2:].decode('ASCII', errors='ignore')
                        # i-Telex may pad with \x00 (e.g. "nc\x00"); remove padding
                        aa = aa.rstrip('\x00')
                        l.info('i-Telex connection rejected, reason {!r}'.format(aa))
                        aa = bmc.translate(aa)
                        with self._rx_lock:
                            self._rx_buffer.append('\x1bA')
                            for a in aa:
                                self._rx_buffer.append(a)
                        break

                    # Acknowledge
                    elif data[0] == 6 and packet_len == 1:
                        l.debug('Received i-Telex packet: Acknowledge ({})'.format(display_hex(data)))
                        if self._connected == ST.CON_INIT:
                            if not self._printer_running:
                                # Request printer start; confirmation will
                                # arrive as ESC-~ (write method will
                                # advance to ST.CON_TP_RUN and do what's in
                                # the following else block)
                                self._connected = ST.CON_TP_REQ
                                with self._rx_lock: self._rx_buffer.append('\x1bA')
                            else:
                                # Printer already running; welcome banner
                                # will be sent above in next iteration if
                                # we're server
                                self._connected = ST.CON_TP_RUN
                                with self._rx_lock: self._rx_buffer.append('\x1bA')
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
                            time_next_send = time.monotonic() + (unprinted-6)*0.15
                        # Send Acknowledge if printer is running and remote end
                        # has printed all sent characters
                        # ! Better not, this will create an Ack flood !
                        # if self._connected >= ST.CON_FULL and unprinted == 0:
                        #     self.send_ack(s, self._acknowledge_counter)

                        # Send remote printer buffer feedback
                        with self._rx_lock: self._rx_buffer.append('\x1b^' + str(unprinted))

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

                    # Also send Acknowledge packet if triggered by idle function
                    if self._send_acknowledge_idle:
                        self._send_acknowledge_idle = False
                        self.send_ack(s, self._acknowledge_counter)

                # ASCII character(s)
                else:
                    l.debug('Received non-i-Telex data: {} ({})'.format(repr(data), display_hex(data)))

                    if is_server and self._block_ascii:
                        l.warning("Incoming ASCII connection blocked")
                        break

                    if is_ascii is None:
                        l.info('Detected ASCII connection')
                        is_ascii = True
                    elif not is_ascii:
                        l.warning('Detected ASCII connection, but i-Telex was expected')
                        is_ascii = True
                    # NB: This only applies for incoming ASCII connections as
                    # outgoing ones will immediately be connected (even before
                    # the first character is received).
                    if self._connected == ST.CON_INIT:
                        if not self._printer_running:
                            # Request printer start; confirmation will
                            # arrive as ESC-~ (write method will
                            # advance to ST.CON_TP_RUN and do what's in
                            # the following else block)
                            self._connected = ST.CON_TP_REQ
                            with self._rx_lock: self._rx_buffer.append('\x1bA')
                        else:
                            # Printer already running; welcome banner
                            # will be sent above in next iteration if
                            # we're server
                            self._connected = ST.CON_TP_RUN
                            with self._rx_lock: self._rx_buffer.append('\x1bA')
                    data = data.decode('ASCII', errors='ignore').upper()
                    data = txCode.BaudotMurrayCode.translate(data)
                    with self._rx_lock:
                        for a in data:
                            if a == '@':
                                a = '#'
                            self._rx_buffer.append(a)
                            self._received_counter += 1

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
                            # Send Acknowledge if printer is running
                            if self._connected >= ST.CON_FULL:
                                self.send_ack(s, self._acknowledge_counter)

                        if self._tx_buffer:
                            if time_next_send and time.monotonic() < time_next_send:
                                l.debug('Sending paused for {:.3f} s'.format(time_next_send-time.monotonic()))
                                pass
                            else:
                                sent = self.send_data_baudot(s, bmc)
                                sent_counter += sent
                                if sent > 7:
                                    time_next_send = time.monotonic() + (sent-6)*0.15

                        elif (timeout_counter % 15) == 0:   # every 3 sec
                            #self.send_heartbeat(s)
                            pass
                            # Suppress Heartbeat for now
                            #
                            # Background: The spec and personal conversation
                            # with Fred yielded that i-Telex uses Heartbeat
                            # only until the printer has been started. After
                            # that, only Acknowledge is used.
                            #
                            # Complications arise from the fact that some
                            # services in the i-Telex network interpret
                            # Heartbeat just like Acknowledge, i.e. printer is
                            # started and printer buffer empty. Special case is
                            # the 11150 service, which in the current version,
                            # on receiving Heartbeat, sends a WRU whilst the
                            # welcome banner is being printed, causing a
                            # character jumble.


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
        self.disconnect_client()
        if _connected_before != self._connected:
            l.info("State transition: {!s}=>{!s}".format(_connected_before, self._connected))

        # print("process_connection end")


    def send_heartbeat(self, s):
        '''Send heartbeat packet (0)'''
        data = bytearray([0, 0])
        l.debug('Sending i-Telex packet: Heartbeat ({})'.format(display_hex(data)))
        s.sendall(data)


    def send_ack(self, s, printed:int):
        '''Send acknowledge packet (6)'''
        # As per i-Telex specs (r874), the rules for Acknowledge are:
        #
        # 1. SHOULDN'T be sent before either Direct Dial or Baudot Data have
        #    been received once (only if we're being called)
        # 2. SHOULDN'T be sent before printer is started
        # 3. MUST be sent once the teleprinter has been started
        #
        # No. 1 is achieved through self._connected; it is set to ST.CON_TP_REQ
        # once the condition is fulfilled.
        #
        # No. 2 is always fulfilled since the printer is started only after
        # condition 1, or is already running if we're the caller.
        #
        # No. 3 is handled as follows:
        # - Once the teleprinter's start confirmation is received, and No. 1 is
        #   fulfilled, the first Acknowledge is sent (only if we're being called).
        # - Acknowledge packets are sent with the number of printed characters
        #   as argument (self._received_counter - self.get_print_buf_len()) on the
        #   schedule below.
        #
        # The schedule is as follows. Basically, Acknowledge is sent if and
        # only if there are unprinted characters in the buffer, i.e.
        # self.get_print_buf_len() > 0, and is triggered by any one of the
        # following (as per spec):
        #
        # - After a 1 s sending break (NB we don't fulfil this exactly, but it
        #   should suffice)
        # - Acknowledge is received and sent_counter equals the packet's data
        #   field (i.e. the remote side has printed all sent characters)
        # - Baudot Data is received and self.get_print_buf_len() >= 16

        # What must teleprinter driver modules implement to enable proper
        # Acknowledge throttling?
        #
        # They should send the ESC-~ command in the following way:
        # - It must not be sent before the printer has been started
        # - It must be sent at least once when the printer has been started
        # - It should be sent about every 500 ms
        # - Payload is the current buffer length, i.e. the characters still
        #   waiting to be printed
        # - The command shouldn't be sent multiple times for the same payload

        data = bytearray([6, 1, printed & 0xff])
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
            if b not in '<>°%':
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
        try:   # socket can possible be closed by other side
            s.sendall(send)
        except:
            pass


    def send_end_with_reason(self, s, reason):
        '''Send end packet with reason (3), for centralex disconnect'''
        send = bytearray([3, len(reason)])   # End with reason
        send.extend([ord(i) for i in reason])
        l.debug(f'Sending i-Telex packet: End {reason} ({display_hex(send)})')
        try:   # socket can possible be closed by other side
            s.sendall(send)
        except:
            pass

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


    def send_connect_remote(self, s, number, pin):
        '''Send connect remote packet (0x81)'''
        l.info("Sending connect remote")
        send = bytearray([129, 6])   # 81 Connect Remote
        # Number
        number = self._number.to_bytes(length=4, byteorder="little")
        send.extend(number)
        # TNS pin
        tns_pin = self._tns_pin.to_bytes(length=2, byteorder="little")
        send.extend(tns_pin)
        l.debug('Sending i-Telex packet: Connect Remote ({})'.format(display_hex(send)))
        s.sendall(send)


    def send_accept_call_remote(self, s):
        '''Send accept call remote packet (0x84)'''
        send = bytearray([132, 0])   # 84 Accept call remote
        l.debug('Sending i-Telex packet: Accept call remote ({})'.format(display_hex(send)))
        s.sendall(send)

    def send_welcome(self, s):
        '''Send welcome message indirect as a server'''
        with self._rx_lock:
            #self._tx_buffer.extend(list('<<<\r\n'))   # send text
            #self._rx_buffer.append('\x1bT')
            #self._rx_buffer.append('#')
            #self._rx_buffer.append('@')
            self._rx_buffer.append('\x1bI')
        return 24 # fixed length of welcome banner, see txDevMCP


    def socket_recv(self, s, cnt):
        try:
            return s.recv(cnt)
        except (socket.timeout):
            return []
        except (socket.error, OSError):
            return None


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
    # <https://telexforum.de/viewtopic.php?p=34877#p34877>
    #_tns_addresses = [
    #    "tlnserv.teleprinter.net",
    #    "tlnserv2.teleprinter.net",
    #    "tlnserv3.teleprinter.net"
    #]


    @classmethod
    def choose_tns_address(cls):
        """
        Return randomly chosen TNS (Telex number server) address, for load
        distribution.
        """
        _srv = random.choice(cls._tns_addresses)
        l.info('Query TNS: '+_srv)
        return _srv


#######

