#!/usr/bin/python3
# -*- coding: future_fstrings -*-

"""
Simple Telex Twitter Client that doesn't need a listener

requires python-fstrings
pip3 install future-fstrings

To turn this module on add the following to the devices section of the configuration

    "twitterV2" : {
      "type" : "twitterV2",
      "enable" : true,
      "consumer_key" : "kdeueniuaeiceyiueycw",
      "consumer_secret" : "fahlvuaeuwcniinn",
      "access_token" : "fahlvuaeuwcniinn",
      "access_token_secret" : "fahlvuaeuwcniinn",
      "bearer_token" : "fahlvuaeuwcniinn",
      "user_mentions": "mch2022telex" 
    }

This article shows you how to get these credentials, make sure you give your app 'write' rights as well
if you want to tweet from your telex
https://www.jcchouinard.com/twitter-api-credentials/

user_mentions is the user account that you want to print the mentions of.

"""
__author__ = "Frank BreBreedijk"
__license__ = "CC0"
__version__ = "0.0.1"


import threading
import time
import datetime
import queue

import txDevITelexCommon
import txCode

import log
import logging

import socketserver
import socket
import queue

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)


class TelexSocket(txDevITelexCommon.TelexITelexCommon):

    def __init__(self, **params):
        super().__init__()
        self.id = 'socket'
        self.running = True
        self._is_online = False

        # Set up queues and buffets
        self.receive_q = queue.Queue()
        self.send_queues = []

        self.main_thread = threading.Thread(target=self.main_thread_fuction, name="main_socket_thread")
        self.main_thread.start()

        self.server = self.ThreadedTCPServer(
            (
                params.get("host"), 
                params.get("port")
            ), self.ThreadedTCPRequestHandler)
        self.server.data = {}
        self.server.data["receive_q"] = self.receive_q
        self.server.data["send_queues"] = self.send_queues
        self.server.data["running"] = self.running

        ip, port = self.server.server_address
        LOG("Listening on {}:{}".format(ip, port),1)

        # Start a thread with the server -- that thread will then start one
        # more thread for each request
        server_thread = threading.Thread(target=self.server.serve_forever)
        # Exit the server thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()        

    def exit(self):
        self.socket_client.stop()
        self.running = False
        self.thread.join()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            if self._is_online:
                return self._rx_buffer.pop(0)
            else:
                self._is_online = True
                return '\x1bA'


    def write(self, a: str, source: str):
        if len(a) != 1:
            if a == '\x1bA':
                self._is_online = True
            if a == '\x1bZ':
                self._is_online = False
            if a == '\x1bWB':
                self._is_online = True
                self._rx_buffer.append('\x1bA')
            return

        if a not in "<>":
            self._tx_buffer.append(a)

    # =====

    def main_thread_fuction(self):
        """
            Main communicaiton handler
        """
        self._rx_buffer.append(0)
        while self.running:
            if self.receive_q.qsize() > 0 :
                data = self.receive_q.get_nowait()
                if data:
                    lines = data.split("\n")
                    out_lines = []
                    for line in lines:
                        if len(line) > 65:
                            out_lines.append(line[0:64])
                            line = line[65:]
                            while len(line) > 65 :
                                out_lines.append(line[0:64])
                                line = line[65:]
                        out_lines.append(line)
                    msg = "\r\n\r".join(out_lines)
                    text = txCode.BaudotMurrayCode.ascii_to_tty_text(msg)
                    for a in text:
                        self._rx_buffer.append(a)

            if self._tx_buffer:
                a = self._tx_buffer.pop(0)
                data = str(a.encode('ASCII'), 'utf8').lower()
                for q in self.send_queues:
                    if q:
                        q.put(data)

        LOG('end connection', 2)
        self._connected = False

    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        pass

    class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

        def handle(self):
            # Setup queues
            self.send_q = queue.Queue()
            self.server.data["send_queues"].append(self.send_q)
            self.request.settimeout(0.1)
            #self.request.setblocking(False)
            socket_ready = False
            while self.server.data["running"] :
                # Recive data if data can be received
                data = None
                try:
                    data = str(self.request.recv(1024), 'ascii')
                except socket.timeout :
                    # Timeouts are normal.
                    pass
                except socket.error as e :
                    if e.errno == 35:
                        # Socket is not available yet
                        pass
                    else:
                        LOG("Socket error: {}".format(str(e)),1)
                        self.send_q = None
                        return
                else:
                    socket_ready = True
                    if not data:
                        # Connection is closed
                        self.send_q = None
                        return
                    else:
                        self.server.data["receive_q"].put(data)
                # Send data that needs to be send
                data = True
                while data and self.send_q.qsize() > 0 :
                    data = self.send_q.get_nowait()
                    if data :
                        self.request.sendall(bytes(data,'ascii'))

            # Cleaup queue
            self.send_q = None
