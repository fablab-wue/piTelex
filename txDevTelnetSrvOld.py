#!/usr/bin/python3
"""
Telex Device - Telnet Server
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread
from socket import socket, AF_INET, SOCK_STREAM

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase

#######

class TelexTelnetSrv(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = '-'
        self.params = params

        self._port = params.get('port', 6666)

        self._rx_buffer = []

        self.run = True
        self.clients = {}

        self.BUFSIZ = 1024

        self.SERVER = socket(AF_INET, SOCK_STREAM)
        self.SERVER.bind(('', self._port))

        self.SERVER.listen(2)
        #print("Waiting for connection...")
        self.ACCEPT_THREAD = Thread(target=self.accept_incoming_connections, name='TelnetSaic')
        self.ACCEPT_THREAD.start()
        pass


    def __del__(self):
        self.run = False
        #print('__del__ in TelexWebSrv')
        self.SERVER.close()
        super().__del__()
    
    # =====

    def read(self) -> str:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            return
            
        self.broadcast(a)

    # =====

    def accept_incoming_connections(self):
        """Sets up handling for incoming clients."""
        while self.run:
            client, client_address = self.SERVER.accept()
            print("%s:%s has connected." % client_address)
            self.clients[client] = client_address
            Thread(target=self.handle_client, name='TelnetShc', args=(client,)).start()


    def handle_client(self, client):  # Takes client socket as argument.
        """Handles a single client connection."""

        welcome = '-=TELEX=-\r\n'
        client.send(bytes(welcome, "utf8"))
        #msg = "%s has joined the chat!" % name
        #self.broadcast(bytes(msg, "utf8"))

        while self.run:
            msg = client.recv(self.BUFSIZ)
            if msg == b'':   # client has been terminated
                client.close()
                del self.clients[client]
                #self.broadcast(bytes("%s has left the chat." % name, "utf8"))
                break

            aa = msg.decode('UTF8')
            aa = txCode.BaudotMurrayCode.translate(aa)

            self.broadcast(aa)
            for a in aa:
                self._rx_buffer.append(a)


    def broadcast(self, msg:str):
        """Broadcasts a message to all the clients."""

        for sock in self.clients:
            sock.send(bytes(msg, "utf8"))

#######

