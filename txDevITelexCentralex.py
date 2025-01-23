#!/usr/bin/python3
"""
Telex Device - i-Telex Centralex Client for reveiving external calls
"""
__author__      = "Detlef Gerhardt"
__email__       = ""
__copyright__   = "Copyright 2025, *dg*"
__license__     = "GPL3"
__version__     = "0.0.2"

from threading import Thread, Event
import socket
import time
import sys
import enum

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import txDevITelexCommon
from txDevITelexCommon import ST

#                        Code  Len   Data ...
selftest_packet = bytes([0x08, 0x04, 0xDE, 0xCA, 0xFB, 0xAD])

#######
class CTX_ST(enum.IntEnum):
    """
    Represent Centralex connection state
    """
    # Disconnected
    OFFLINE = 1

    # Disconnected
    CHECK_AUTH = 2

    # Standby, waiting for connection
    STANDBY = 3

    # Connected, connected with caller, see status in ST
    CONNECTED = 4

    # occupied by outgoing call
    BUSY = 5

    # Restart connection to Centralex Server
    RECYCLE = 6


class TelexITelexCentralex(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()

        # Sane Id as TelexITelexSrv because it actually replaces it and we do not want to adjust all locations
        # where the Id is used.
        self.id = 'iTs'
        self.params = params

        self._centralex_address = params.get('centralex_srv');
        self._centralex_port = params.get('centralex_port', 49491);

        self._number = int(params.get('tns_dynip_number', 0))
        if self._number < 10000 or self._number > 0xffffffff:
            # Own number must be a valid 32-bit integer with at least 5 digits.
            # client_update requires this, so ignore faulty number
            l.warning("Invalid own number, ignored: " + repr(self._number))
            self._number = None

        self._tns_pin = params.get('tns_pin', None)

        if self._tns_pin < 0 or self._tns_pin > 0xffff:
            # TNS pin no valid integer inside 16 bit; client_update requires
            # this though, so ignore
            l.warning("Invalid TNS pin, ignored: " + repr(self._tns_pin))
            self._number = None
            self._tns_pin = None

        # TODO: put this in the json file
        TelexITelexCentralex._tns_addresses = params.get('tns_srv',['tlnserv.teleprinter.net','tlnserv2.teleprinter.net','tlnserv3.teleprinter.net'])

        # TODO: put this in the json file
        self._tns_port = params.get('tns_port', 11811)

        self._block_ascii = params.get('block_ascii', True)

        #self.clients = {}

        # self._ctx_recycle = False
        self._ctx_occ_reason = ''

        self.handle_centralex_connection()

        # Record number of failed tests and TNS updates
        #self.update_tns_fail = 0
        self.test_connection_fail = 0

        # Threading event for self-test coordination
        self.selftest_event = Event()

        # Flag for printer start timeout; terminate connection if it did
        self.printer_start_timed_out = False

        # Flag for blocking inbound connections when an outbound one is active
        self.block_inbound = False

        # Create event just for sleeping. The event is only triggered on
        # quitting piTelex, to wake up everyone still sleeping.
        self.term = Event()


    # =====

    def handle_centralex_connection(self):
        Thread(target=self.thread_handle_centralex_connection, name='iTelexCtxHC').start()

    # =====

    def thread_handle_centralex_connection(self):
        reconnect_after_error = 15 # wait 15 sec. after error before try to reconnect to centralex server
        reconnect_after_conn = 2 # wait 2 sec. after connection before reconnect to centralex server

        self._ctx_st = CTX_ST.OFFLINE
        last_recv_ack = 0.0
        last_send_ack = 0.0

        while True:
            try:
                if not self._run:
                    s.close()
                    return

                if len(self._ctx_occ_reason) > 0:
                    self.send_end_with_reason(s, self._ctx_occ_reason);
                    s.close()
                    self._ctx_occ_reason = ''
                    self._ctx_st == CTX_ST.BUSY

                elif self._ctx_st == CTX_ST.BUSY:
                    time.sleep(0.1)

                elif self._ctx_st == CTX_ST.RECYCLE:
                    s.close();
                    self._ctx_st = CTX_ST.OFFLINE

                elif self._ctx_st == CTX_ST.OFFLINE:
                    # connect to centralex server
                    l.info(f'Centralex: connecting to server {self._centralex_address}:{self._centralex_port})')
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    address = (self._centralex_address, int(self._centralex_port))
                    s.settimeout(5.0) # Wait at most 5 s during connect
                    s.connect(address)
                    self.send_connect_remote(s, self._number, self._tns_pin)
                    self._ctx_occ_reason = ''
                    self._ctx_st = CTX_ST.CHECK_AUTH

                elif self._ctx_st == CTX_ST.CHECK_AUTH:
                    s.settimeout(1)
                    data = s.recv(2)

                    if (data[0] == 0x82 and data[1] == 0x00):
                        # Remote confirm
                        last_recv_ack = time.time()
                        last_send_ack = 0.0
                        with self._rx_lock: self._rx_buffer.append('\x1bCC')
                        l.info('Centralex: socket connected')
                        self._ctx_st = CTX_ST.STANDBY
                    else:
                        # Error: invalid response (authentication error)
                        l.warning(f'Centralex: authentication failed data={data[0]}')
                        with self._rx_lock: self._rx_buffer.append('\x1bCE')
                        self._ctx_st = CTX_ST.RECYCLE
                        time.sleep(reconnect_after_error)

                elif self._ctx_st == CTX_ST.STANDBY:
                    t = time.time()
                    if (t - last_recv_ack > 35):
                        # Error: heartbeat timeout from centralex server
                        l.warning('Centralex: heartbeat timeout: {!s} sec'.format(t - last_recv_ack))
                        self._ctx_st = CTX_ST.RECYCLE
                        # s.close()
                        time.sleep(reconnect_after_error)
                    if (t - last_send_ack > 15):
                        self.send_heartbeat(s)
                        last_send_ack = t
                    s.settimeout(0.2)
                    try:
                        data = s.recv(1)
                    except (socket.timeout):
                        continue

                    if data == None:
                        # connection lost
                        self._ctx_st = CTX_ST.RECYCLE
                        time.sleep(reconnect_after_error)
                        continue
                    
                    if data[0] != 0x00 and data[0] != 0x83:
                        l.debug(f'Centralex: ignore invalid data {data[0]}')
                        continue;

                    try:
                        d = s.recv(1)
                    except (socket.timeout):
                        continue

                    data += d

                    if (data[0] == 0x00 and data[1] == 0x00):
                        # Heartbeat from centralex server
                        # l.debug('Heartbeat from centralex')
                        last_recv_ack = t

                    elif (data[0] == 0x83 and data[1] == 0x00):
                        # incoming remote call from centralex server
                        self.send_accept_call_remote(s)
                        self._ctx_st = CTX_ST.CONNECTED
                        self.process_connection(s, True, False)
                        with self._rx_lock: self._rx_buffer.append('\x1bST') # stop teleprinter
                        self._printer_running = False
                        self.send_end_with_reason(s, 'nc')
                        # s.close()
                        self._ctx_st = CTX_ST.RECYCLE
                        time.sleep(reconnect_after_conn)

            except (socket.timeout):
                l.debug(f'Centralex: socket timeout ctx_st={self._ctx_st}')
                with self._rx_lock: self._rx_buffer.append('\x1bCE')
                self._ctx_st = CTX_ST.RECYCLE
                time.sleep(reconnect_after_error)
            except OSError as e:
                l.debug(f'Centralex: error ctx_st={self._ctx_st} e={e}')
                with self._rx_lock: self._rx_buffer.append('\x1bCE')
                self._ctx_st = CTX_ST.RECYCLE
                time.sleep(reconnect_after_error)

    # =====

    def read(self) -> str:
        with self._rx_lock:
            if self._rx_buffer:
                if ST.DISCON < self._connected <= ST.CON_TP_RUN:
                    # Welcome banner hasn't been sent yet. Pop only non-printable
                    # items.
                    for nr, item in enumerate(self._rx_buffer):
                        if item.startswith('\x1b'):
                            return self._rx_buffer.pop(nr)
                else:
                    return self._rx_buffer.pop(0)
    # =====

    def write(self, a:str, source:str):
        super().write(a, source)
        if len(a) != 1:
            if self._connected <= ST.DISCON:
                if a in ('\x1bWB', '\x1bA'):
                    # Ready-to-dial or printer start states triggered: There is
                    # an outgoing connection. Block inbound ones.
                    self.block_inbound = True
                    l.debug("Blocking inbound connections")
                elif a == '\x1bZ':
                    # Connection ended, unblock
                    self.block_inbound = False
                    l.debug("Unblocking inbound connections")
            elif self._connected > ST.DISCON:
                if a == '\x1bZ':   # end session
                    if self._connected < ST.CON_TP_RUN and source == 'MCP':
                        # Printer start failed, initiate disconnect with error
                        # message
                        self.printer_start_timed_out = True
                    else:
                        # Printer had already been started, disconnect normally
                        self.disconnect_client()
                elif self._connected == ST.CON_TP_RUN and a == '\x1bWELCOME' and source == 'MCP':
                    # MCP says: Welcome banner has been received completely. Enable
                    # non-command reads in read method so that normal communication
                    # can begin.
                    self._connected = ST.CON_FULL

            if self._ctx_st != CTX_ST.BUSY:
                if a == '\x1bA':
                    # print("busy")
                    self._ctx_st = CTX_ST.BUSY
                    self._ctx_occ_reason = 'occ'

            else:
                if a == '\x1bZ':
                    # print("not busy")
                    self._ctx_st = CTX_ST.OFFLINE

            return


        if source in ['iTc', 'iTs']:
            # Don't send back data from ITelexClient/Srv
            return

        self._tx_buffer.append(a)

    # =====

    def test_connection(self):
        """
        Test if we can connect to ourselves. That's as much as we can do to
        check our external reachability. Nonstandard LAN routing setups may
        cause this to fail though, even if we're reachable externally.

        return True on success, an error string otherwise.

        For details, see implementation and i-Telex Communication Specification
        (r874).
        """
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((self.ip_address, self._port))
                qry = selftest_packet
                # Reset selftest event before sending in case it was
                # accidentally triggered before
                self.selftest_event.clear()
                s.sendall(qry)
                s.close()
                # Wait for confirmation from server thread
                ret = self.selftest_event.wait(timeout = 1.0)
                if not ret:
                    ret = "self-test timeout"
                self.selftest_event.clear()
                return ret

        except Exception as e:
            return str(e)
        """
#######

