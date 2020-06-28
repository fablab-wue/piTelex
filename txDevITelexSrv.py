#!/usr/bin/python3
"""
Telex Device - i-Telex Server for reveiving external calls
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread
import socket

import txCode
import txBase
import log
import txDevITelexCommon

#######

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;44m<'+text+'>\033[0m', level)

class TelexITelexSrv(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()

        self.id = '<'
        self.params = params

        self._port = params.get('port', 2342)

        self.run = True
        self.clients = {}

        self.SERVER = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SERVER.bind(('', self._port))

        self.SERVER.listen(2)
        #print("Waiting for connection...")
        Thread(target=self.thread_srv_accept_incoming_connections, name='iTelexSrvAC').start()


    def exit(self):
        self._run = False
        self.disconnect_client()
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
            try:
                client, client_address = self.SERVER.accept()
                LOG("%s:%s has connected" % client_address, 3)
                if self.clients:   # one client is active!
                    self.send_reject(client)
                    client.close()
                    continue
                self.clients[client] = client_address
                self._tx_buffer = []
                Thread(target=self.thread_srv_handle_client, name='iTelexSrvHC', args=(client,)).start()
            except:
                return

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

#######

