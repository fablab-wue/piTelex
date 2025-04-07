#!/usr/bin/python3
# -*- coding: future_fstrings -*-

"""
Simple Telex Socket Client

To turn this module on add the following to the devices section of the configuration

        "socket": {
            "type": "socket",
            "enable": true,
            "host" : "127.0.0.1",
            "port" : 31337
          }
        },

"""
__author__ = "Frank Breedijk"
__license__ = "CC0"
__version__ = "0.0.1"

import txBase
import txCode

import log
import logging

import socket
import select

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)


class TelexSocket(txBase.TelexBase):

    def __init__(self, **params):
        super().__init__()
        self.id = 'socket'
        self._rx_buffer = []

        # Create a TCP/IP socket
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setblocking(0)

        # Bind the socket to the port
        server_address = (
            params.get("host"),
            params.get("port")
        )
        self._server.bind(server_address)

        # Listen for incoming connections
        self._server.listen(5)
        LOG("Listening on {}:{}".format(params.get("host"), params.get("port")),1)

        # Sockets from which we expect to read
        self._sockets = [ self._server ]

        # Telex encoding
        self._coding = params.get("coding", 0 )


    def exit(self):
        for s in self._sockets :
            if not s is self._server:
                s.close()
        self._server.close()

    def __del__(self):
        super().__del__()

    # =====

    def read(self) -> str:

        # Timeout is set to null so select doesn;t wait, but polls. Empty lists will be returned if
        # there are no sockets in the desired states
        readable, writable, exceptional = select.select(self._sockets, self._sockets, self._sockets, 0)
        # Handle input sockets
        for s in readable:
            if s is self._server:
                # A "readable" server socket is ready to accept a connection
                connection, client_address = s.accept()
                LOG("New connection from {}:{}".format(client_address[0],client_address[1]),1)
                # Set the connection to non-blocking
                connection.setblocking(0)
                self._sockets.append(connection)
            else:
                data = s.recv(102400)
                if data:
                    # A readable client socket has data
                    text = data.decode('utf-8', 'replace').replace('\ufffd','?')

                    # Transform to Telex encoding an keep within 68 character width
                    linewidth = 68
                    out_lines = []
                    for line in text.split("\n"):
                        bmc = txCode.BaudotMurrayCode.ascii_to_tty_text(line.strip(), coding=self._coding)
                        bmc = bmc.replace("@","(A)")
                        while len(bmc) >= linewidth:
                            out_lines.append(bmc[0:linewidth])
                            bmc = bmc[linewidth:]
                        out_lines.append(bmc)
                    txt_out = "\r\n\r".join(out_lines)

                    # Append it to the _rx_buffer char by char
                    for c in txt_out:
                        self._rx_buffer.append(c)
                else:
                    # Interpret empty result as closed connection
                    # Remove the socket from the sockets list and close it
                    self._sockets.remove(s)
                    s.close()

        # Return the first character of the rx_buffer to the chain if we have it
        if self._rx_buffer:
            return self._rx_buffer.pop(0)

        return

    def write(self, a: str, source: str):
        if len(a) != 1:
            return



        # Timeout is set to null so select doesn;t wait, but polls. Empty lists will be returned if
        # there are no sockets in the desired states
        readable, writable, exceptional = select.select(self._sockets, self._sockets, self._sockets, 0)
        # Send the character that needs to be written to all writable sockets.
        for s in writable:
            s.send(a.encode('utf-8', 'replace'))

