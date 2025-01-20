#!/usr/bin/python3
"""
Telex Device - i-Telex Server for reveiving external calls
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread, Event
import socket
import time
import sys

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import txDevITelexCommon
from txDevITelexCommon import ST

#                        Code  Len   Data ...
selftest_packet = bytes([0x08, 0x04, 0xDE, 0xCA, 0xFB, 0xAD])

#######

class TelexITelexSrv(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()

        self.id = 'iTs'
        self.params = params

        port = params.get('port', 0)
        if port > 0:
            self._local_port = port
            self._public_port = port
        else:
            self._local_port = params.get('local_port', 2342)
            self._public_port = params.get('public_port', 2342)

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

        TelexITelexSrv._tns_addresses = params.get('tns_srv',['tlnserv.teleprinter.net','tlnserv2.teleprinter.net','tlnserv3.teleprinter.net'])

        self._tns_port = params.get('tns_port',11811)

        self._block_ascii = params.get('block_ascii', True)

        self.clients = {}

        self.SERVER = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set socket option to bind in spite of TIME_WAIT connections. This is
        # to facilitate rapid restarting if necessary (rapid meaning < 2*MSL or
        # < 240 s).
        # https://stackoverflow.com/questions/5040491/python-socket-doesnt-close-connection-properly
        self.SERVER.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.SERVER.bind(('', self._local_port))

        # Set timeout for server socket so that calling accept will not block
        # indefinitely. Otherwise, the server thread would prevent quitting
        # piTelex.
        self.SERVER.settimeout(2.0)

        self.SERVER.listen(2)
        #print("Waiting for connection...")
        Thread(target=self.thread_srv_accept_incoming_connections, name='iTelexSrvAC').start()

        # Record number of failed tests and TNS updates
        self.update_tns_fail = 0
        self.test_connection_fail = 0

        # Own public IP address; updated by TNS queries
        self.ip_address = None

        # Threading event for self-test coordination
        self.selftest_event = Event()

        # Flag for printer start timeout; terminate connection if it did
        self.printer_start_timed_out = False

        # Flag for blocking inbound connections when an outbound one is active
        self.block_inbound = False

        # Create event just for sleeping. The event is only triggered on
        # quitting piTelex, to wake up everyone still sleeping.
        self.term = Event()

        if self._number:
            # Own number given: update own information in TNS (telex number
            # server) if needed
            Thread(target=self.thread_handle_tns_update, name='iTelexTNSupd').start()

    def exit(self):
        self._run = False
        self.term.set()
        self.disconnect_client()
        self.SERVER.close()

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
            return

        if source in ['iTc', 'iTs']:
            # Don't send back data from ITelexClient/Srv
            return

        self._tx_buffer.append(a)

    # =====

    def thread_srv_accept_incoming_connections(self):
        """Sets up handling for incoming clients."""
        while self._run:
            try:
                client, client_address = self.SERVER.accept()
            except ConnectionAbortedError:
                # This exception results from ECONNABORT from "under the hood".
                # It happens if the client resets the connection after it is
                # established, but before accept is called:
                #
                # - C => S: SYN
                # - C <= S: SYN, ACK
                # - C => S: ACK
                # - C => S: RST
                # - accept called now: ConnectionAbortedError!
                #
                # The only reasonable thing to do is to ignore it.
                l.info("Exception caught:", exc_info = sys.exc_info())
                continue
            except (socket.timeout, OSError):
                # Socket timed out: Just check if we're still running
                # (self._run) and recall accept. This serves to not prevent
                # shutting down piTelex.
                #
                # An OSError can occur on quitting piTelex, if the server
                # socket is closed before accept returns. Ignore.
                continue
            # Recognise self-tests early and mute them
            if client_address[0] == self.ip_address:
                data = client.recv(128)
                if data == selftest_packet:
                    # Signal self-test thread that we received the packet
                    self.selftest_event.set()
                    client.close()
                    continue
            l.info("%s:%s has connected" % client_address)
            if self.clients or self.block_inbound or self._connected != ST.DISCON:
                # Our line is occupied (occ), reject client. Little issue here:
                # ASCII clients get an i-Telex package. But the content should
                # be readable enough to infer our message.
                self.send_reject(client, "occ")
                l.warning("Rejecting client (occupied)")
                client.close()
                continue
            self.clients[client] = client_address
            self._tx_buffer = []
            Thread(target=self.thread_srv_handle_client, name='iTelexSrvHC', args=(client,)).start()


    def thread_srv_handle_client(self, s):  # Takes client socket as argument.
        """Handles a single client connection."""
        try:
            self.process_connection(s, True, None)

        except Exception:
            l.error("Exception caught:", exc_info = sys.exc_info())
            self.disconnect_client()

        s.close()

# rowo don't force Z mode (would wake up from ZZ...), but trigger transit to sleep
#        with self._rx_lock: self._rx_buffer.append('\x1bZ')
        with self._rx_lock: self._rx_buffer.append('\x1bST')
        self._printer_running = False
        del self.clients[s]

    def thread_handle_tns_update(self):
        """
        Check connection self-test status and act accordingly.

        For details, see implementation and i-Telex Communication Specification
        (r874).

        Some things aren't in the specs, but were obtained by personal
        communication with i-Telex programmer Fred Sonnenrein. i-Telex does it
        like this:

        1. Depending on configuration, do self-test every 45 s (not too often
           because self test blocks other connections).
        2. If self-test fails, retry two times. On success, go to 1. If three
           consecutive self tests fail, continue.
        3. Trigger client_update to TNS and reset timer (see 6).
        4. If this yielded data, retry self-test at most three times. On
           success, go to 1. Continue otherwise.
        5. Log error and wait until client_update successful, in this case go
           to 1.
        6. The previous items nonwithstanding, retry client_update every 60
           min. If client_update is triggered elsewhere, reset timer.

        Modifications for piTelex, to KISS:

        - Run everything from single thread. Instead of precise timings, use
          sleep in-between calls.
        - Do self-test every 20 s (no problem as we don't block "real"
          clients), rinse and repeat. Retry up to six times on fail.
        - After first six fails, trigger client_update. Retry self-test another
          six times. If it fails another six times, stop self-tests and keep
          trying client_update. Restart self-tests if successful.
        - The only gap: If TNS updates don't succeed but self-tests do, there
          is no advance warning. If eventually the IP address changed and the TNS
          update still cannot be performed, the self test will fail and the
          problem will be noticed only then.

        """
        while self._run:
            # Update TNS record on startup to obtain own IP address. After
            # that, update on hourly schedule (roughly).
            result = self.update_tns_record()
            if result is True:
                self.update_tns_fail = 0
                # If update succeeded, restart self-test
                if self.test_connection_fail == 666:
                    l.info("self-test: TNS update successful, resuming self-test")
                    self.test_connection_fail = 0
                else:
                    l.debug("self-test: TNS update successful")
            else:
                self.update_tns_fail += 1
                l.warning("self-test: TNS update failed {}x ({})".format(self.update_tns_fail, result))

            # Startup: As long as own IP address not known, self-test not
            # possible. Retry.
            if not self.ip_address:
                l.error("self-test: IP address unknown, connection test impossible, retrying in 60 min")
                # Sleep and break only if application is terminated, carry on otherwise
                if self.term.wait(3600): break
                continue

            for _ in range(180):
                # Self-test every 20 s for about one hour, then exit this loop
                # and restart while loop, updating TNS record.

                # Sleep and break only if application is terminated, carry on otherwise
                if self.term.wait(20): break

                # If 2*6 self-tests fail consecutively, cease self-testing and
                # only retry TNS update hourly.
                if self.test_connection_fail >= 12:
                    if self.test_connection_fail == 12:
                        l.error("self-test: too many connection tests failed, retrying after next TNS update")
                        # TODO print error with date
                    # cheap trick to only log and print the error once, and
                    # allow proper resetting above
                    self.test_connection_fail = 666
                    continue

                # OTOH, if self-test failed six times, but less than 12,
                # continue self-testing no matter if the TNS update succeeded.

                # Do connection self-test. Count failures, reset on success.
                test_result = self.test_connection()
                if test_result is True:
                    self.test_connection_fail = 0
                    l.debug("self-test: connection test successful")
                else:
                    self.test_connection_fail += 1
                    l.warning("self-test: connection test failed {}x ({})".format(self.test_connection_fail, test_result))

                if self.test_connection_fail == 6:
                    # After six failed tries, update TNS immediately.
                    break

    def test_connection(self):
        """
        Test if we can connect to ourselves. That's as much as we can do to
        check our external reachability. Nonstandard LAN routing setups may
        cause this to fail though, even if we're reachable externally.

        return True on success, an error string otherwise.

        For details, see implementation and i-Telex Communication Specification
        (r874).
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((self.ip_address, self._public_port))
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

    def update_tns_record(self):
        """
        Update own record on TNS server. Primary function: When the own ip
        address changes (e.g. because of a forced internet disconnection),
        publish the new address with the TNS.

        return True on success, an error string otherwise.

        For details, see implementation and i-Telex Communication Specification
        (r874).
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
#                self._tns_port = 11811
                s.connect((self.choose_tns_address(), self._tns_port))
                # client_update packet:
                #                Code  Len
                qry = bytearray([0x01, 0x08])
                # Number
                number = self._number.to_bytes(length=4, byteorder="little")
                qry.extend(number)
                # TNS pin
                tns_pin = self._tns_pin.to_bytes(length=2, byteorder="little")
                qry.extend(tns_pin)
                # Port
                port = self._public_port.to_bytes(length=2, byteorder="little")
                qry.extend(port)
                s.sendall(qry)
                data = s.recv(1024)
                s.close()
            if data[0] == 0x02: # Address_confirm
                if not data[1] == 0x4:
                    raise ValueError("Address_Confirm should have length 0x4, but has 0x{0:x} instead".format(data[1]))
                # IP address
                ip_address = ".".join([str(i) for i in data[2:6]])
                self.ip_address = ip_address
                return True
            else: # Different type: dissect and log
                msg_type = data[0]
                length = data[1]
                content = data[2:]
                raise Exception("Unexpected answer to Address_confirm: type 0x{0:x}, content: ".format(msg_type), repr(content))

        except Exception as e:
            return str(e)

#######

