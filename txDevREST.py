#!/usr/bin/python3
"""
Telex Device - REST

"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread
#import ssl
import socket
import time
import json

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import log

#######

def LOG(text:str, level:int=3):
    log.LOG('\033[30;46m<'+text+'>\033[0m', level)


class TelexREST(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = '/'
        self.params = params


    def exit(self):
        #self.disconnect_client()
        pass

    # =====

    def read(self) -> str:
        pass


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bZ':   # end session
                try:
                    with open('x.json', 'r') as fp:
                        msg = json.load(fp)
                    self.connect_client(msg)
                except Exception as e:
                    LOG(str(e))
            return


        #self._tx_buffer.append(a)
        #return True   #debug


    def idle(self):
        pass

    # =====

    def connect_client(self, msg):
        Thread(target=self.thread_connect_as_client, name='REST', args=(msg,)).start()

    # =====

    def thread_connect_as_client(self, msg):
        try:
            # connect to destination Telex

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_base:
                if msg.get('SSL', False):
                    s = ssl.wrap_socket(s_base)
                else:
                    s = s_base
                LOG('connected to '+msg['Name'], 3)
                address = (msg['Host'], int(msg['Port']))
                s.connect(address)

                a = msg['Text']
                a = a.replace('\\r', '\r')
                a = a.replace('\\n', '\n')
                data = a.encode('UTF-8')
                s.sendall(data)
                LOG('SEND',1)
                time.sleep(3)

        except Exception as e:
            LOG(str(e))

        #s.close()

    # =====


#######

