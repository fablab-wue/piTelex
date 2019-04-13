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

#######

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;44m<'+text+'>\033[0m', level)

class TelexIRC(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = '<'
        self.params = params

        self._channel = params.get('channel', '#fablab')

        self._rx_buffer = []
        self._tx_buffer = []
        self._connected = False
        self.run = True

        #print("Waiting for connection...")
        Thread(target=self.thread_IRC_connection, name='IRC').start()


    def exit(self):
        self._run = False

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)



    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bZ':   # end session
                pass
                #self.disconnect_client()
            return

        self._tx_buffer.append(a)

    # =====

    def thread_IRC_connection(self):
        """Sets up handling for incoming clients."""

        # connect to IRC serer

        while self.run:
            try:


                data = 'Lorem ipsum'

                data = data.decode('ASCII', errors='ignore').upper()
                data = txCode.BaudotMurrayCode.translate(data)
                for a in data:
                    self._rx_buffer.append(a)



                if self._tx_buffer:
                    a = self._tx_buffer.pop(0)
                    data = a.encode('ASCII')
                    #send_to_IRC(data)

            except socket.error:
                LOG('ERROR socket', 2)
                break


        LOG('end connection', 3)
        self._connected = False

#######

