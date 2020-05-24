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

import txCode
import txBase
import log
import txDevITelexCommon

#                        Code  Len   Data ...
selftest_packet = bytes([0x08, 0x04, 0xDE, 0xCA, 0xFB, 0xAD])

#######

def LOG(text:str, level:int=3):
    log.LOG('\033[30;44m<'+text+'>\033[0m', level)

class TelexITelexSrv(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()

        self.id = '<'
        self.params = params

        self._port = params.get('port', 2342)

        self._number = int(params.get('number', 0))
        if self._number <= 0 or self._number > 0xffffffff:
            # Own number no valid integer inside 32 bit; client_update requires
            # this though, so ignore
            LOG("Invalid own number, ignored: " + repr(self._number), level=2)
            self._number = None

        self._tns_pin = params.get('tns-pin', None)
        if self._tns_pin < 0 or self._tns_pin > 0xffff:
            # TNS pin no valid integer inside 16 bit; client_update requires
            # this though, so ignore
            LOG("Invalid TNS pin, ignored: " + repr(self._tns_pin), level=2)
            self._number = None
            self._tns_pin = None

        self.run = True
        self.clients = {}

        self.SERVER = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SERVER.bind(('', self._port))

        self.SERVER.listen(2)
        #print("Waiting for connection...")
        Thread(target=self.thread_srv_accept_incoming_connections, name='iTelexSaic').start()

        # State of connection self-test, wherein we verify if we can connect to
        # ourselves by our external IP address.
        # - 0: need to update TNS, current own public IP address unknown
        # - 1: connection not ok or untested, own public IP address known
        # - 2: connection ok
        self.connection_test_state = 0

        # Own public IP address; updated by TNS queries
        self.ip_address = None

        # Threading event for self-test coordination
        self.selftest_event = Event()

        if self._number:
            # Own number given: update own information in TNS (telex number
            # server) if needed
            Thread(target=self.thread_handle_tns_update, name='iTelexTNSupd').start()

    def exit(self):
        self.disconnect_client()
        self._run = False
        self.SERVER.close()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)



    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bZ':   # end session
                self.disconnect_client()
            return

        if source in '<>':
            return

        self._tx_buffer.append(a)

    # =====

    def thread_srv_accept_incoming_connections(self):
        """Sets up handling for incoming clients."""
        while self.run:
            client, client_address = self.SERVER.accept()
            # Recognise self-tests early and mute them
            if client_address[0] == self.ip_address:
                data = client.recv(128)
                if data == selftest_packet:
                    # Signal self-test thread that we received the packet
                    self.selftest_event.set()
                client.close()
                continue
            LOG("%s:%s has connected" % client_address, 3)
            if self.clients:   # one client is active!
                self.send_reject(client)
                client.close()
                continue
            self.clients[client] = client_address
            self._tx_buffer = []
            Thread(target=self.thread_srv_handle_client, name='iTelexShc', args=(client,)).start()


    def thread_srv_handle_client(self, s):  # Takes client socket as argument.
        """Handles a single client connection."""
        try:
            self._rx_buffer.append('\x1bA')

            self.process_connection(s, True, None)

        except Exception as e:
            LOG(str(e))
            self.disconnect_client()

        s.close()
        self._rx_buffer.append('\x1bZ')
        del self.clients[s]

    def thread_handle_tns_update(self):
        """
        Check connection self-test status and act accordingly.

        For details, see implementation and i-Telex Communication Specification
        (r874).
        """
        while self.run:
            if self.connection_test_state <= 0:
                # Current own public address unknown, need to update with TNS
                # servers. They'll send us our public address in the
                # address_confirm packet.
                #
                # Sleep for a while if unsuccessful to prevent spamming them.
                if self.update_tns_record():
                    # We successfully updated the TNS record and got our public IP
                    self.connection_test_state = 1
                    LOG("self-test status => 1", level=5)
                else:
                    # An error occurred: Wait before retrying
                    time.sleep(60)

            elif self.connection_test_state == 1:
                # Connection status not ok or unknown. Need to verify now.
                if self.test_connection():
                    self.connection_test_state = 2
                    LOG("self-test status => 2", level=5)
                else:
                    # Two possibilities here:
                    # - Our IP address has changed: Need to update TNS record!
                    # - Our internet connection is borked: No general solution
                    #   available, unfortunately. Fall back to TNS update.
                    # But wait a few seconds before updating, maybe the
                    # DSL/Wifi reappears until then.
                    self.connection_test_state = 0
                    LOG("self-test status => 0", level=2)
                    time.sleep(10)

            elif self.connection_test_state >= 2:
                # Connection tested ok. Wait until rechecking.
                time.sleep(200) # Specs suggest 200 s
                self.connection_test_state = 1
                LOG("self-test status => 1", level=5)

    def test_connection(self):
        """
        Test if we can connect to ourselves. That's as much as we can do to
        check our external reachability. Nonstandard LAN routing setups may
        cause this to fail though, even if we're reachable externally.

        return True on success, False otherwise.

        For details, see implementation and i-Telex Communication Specification
        (r874).
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect((self.ip_address, self._port))
                qry = selftest_packet
                # Reset selftest event before sending in case it was
                # accidentally triggered before
                self.selftest_event.clear()
                s.sendall(qry)
                s.close()
                # Wait for confirmation from server thread
                ret = self.selftest_event.wait(timeout = 1.0)
                self.selftest_event.clear()
                return ret

        except Exception as e:
            LOG(str(e) + ", {}:{}".format(self.ip_address, self._port), level=2)
            return False

    def update_tns_record(self):
        """
        Update own record on TNS server. Primary function: When the own ip
        address changes (e.g. because of a forced internet disconnection),
        publish the new address with the TNS.

        return True on success, False otherwise.

        For details, see implementation and i-Telex Communication Specification
        (r874).
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                self._tns_port = 11811
                s.connect((choose_tns_address(), self._tns_port))
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
                port = self._port.to_bytes(length=2, byteorder="little")
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
            LOG(str(e), level=2)
            return False

#######

