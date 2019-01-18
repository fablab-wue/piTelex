#!/usr/bin/python
"""
i-Telex Server
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txCode
import txBase
#from socket import AF_INET, socket, SOCK_STREAM
import socket
from threading import Thread

#######

def LOG(text:str):
    print('\033[5;30;44m<'+text+'>\033[0m', end='', flush=True)

class TelexITelexSrv(txBase.TelexBase):
    def __init__(self, **params):
        #, port:int

        super().__init__()

        self.id = '>'
        self.params = params

        self._port = params.get('port', 2342)

        self._rx_buffer = []
        self._tx_buffer = []
        self._received = 0

        self.run = True
        self.clients = {}

        self.BUFSIZ = 1024

        self.SERVER = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SERVER.bind(('', self._port))

        self.SERVER.listen(2)
        #print("Waiting for connection...")
        Thread(target=self.thread_accept_incoming_connections).start()


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
            
        self._tx_buffer.append(a)

    # =====

    def thread_accept_incoming_connections(self):
        """Sets up handling for incoming clients."""
        while self.run:
            client, client_address = self.SERVER.accept()
            LOG("%s:%s has connected" % client_address)
            self.clients[client] = client_address
            self._tx_buffer = []
            Thread(target=self.thread_handle_client, args=(client,)).start()


    def thread_handle_client(self, client):  # Takes client socket as argument.
        """Handles a single client connection."""
        mc = txCode.BaudotMurrayCode()
        mc.flip_bits = True
        is_ascii = False

        client.settimeout(0.2)

        while self.run:
            try:
                data = client.recv(1)
                
                if not data:   # lost connection
                    break

                elif data[0] <= 9:   # i-Telex packet
                    is_ascii = False
                    d = client.recv(1)
                    data += d
                    plen = d[0]
                    data += client.recv(plen)

                    if data[0] == 0:   # Heartbeat
                        #LOG('Heartbeat '+repr(data))
                        pass

                    elif data[0] == 1:   # Direct Dial
                        LOG('Direct Dial '+repr(data))
                        pass

                    elif data[0] == 2 and plen > 0:   # Baudot data
                        #LOG('Baudot data '+repr(data))
                        aa = mc.decodeB2A(data[2:])
                        for a in aa:
                            if a == '@':
                                a = '#'
                            self._rx_buffer.append(a)
                        self._received += len(data[2:])
                        self.send_ack(client)

                    elif data[0] == 3:   # End
                        LOG('End '+repr(data))
                        break

                    elif data[0] == 4:   # Reject
                        LOG('Reject '+repr(data))
                        break

                    elif data[0] == 6 and plen == 1:   # Acknowledge
                        #LOG('Acknowledge '+repr(data))
                        LOG(str(data[2]))
                        pass

                    elif data[0] == 7 and plen >= 1:   # Version
                        #LOG('Version '+repr(data))
                        self.send_version(client)

                    elif data[0] == 8:   # Self test
                        LOG('Self test '+repr(data))
                        pass

                    elif data[0] == 9:   # Remote config
                        LOG('Remote config '+repr(data))
                        pass

                else:   # ASCII character(s)
                    #LOG('Other', repr(data))
                    is_ascii = True
                    data = data.decode('ASCII', errors='ignore')
                    data = txCode.BaudotMurrayCode.translate(data)
                    for a in data:
                        if a == '@':
                            a = '#'
                        self._rx_buffer.append(a)


            except socket.timeout:
                #LOG('.')
                if self._tx_buffer:
                    if is_ascii:
                        self.send_data_ascii(client)
                    else:
                        self.send_data_baudot(client, mc)
                else:
                    if not is_ascii:
                        self.send_heartbeat(client)


            except socket.error:
                LOG('Error socket')
                break


        LOG('end connection')
        client.close()
        del self.clients[client]


    def send_heartbeat(self, s):
        data = bytearray([0, 0])
        s.sendall(data)


    def send_ack(self, s):
        data = bytearray([6, 1, self._received & 0xff])
        s.sendall(data)


    def send_version(self, s):
        send = bytearray([7, 1, 1])
        s.sendall(send)


    def send_data_ascii(self, s):
        a = self._tx_buffer.pop(0)
        data = a.encode('ASCII')
        s.sendall(data)


    def send_data_baudot(self, s, mc):
        data = bytearray([2, 0])
        while self._tx_buffer and len(data) < 100:
            a = self._tx_buffer.pop(0)
            bb = mc.encodeA2B(a)
            if bb:
                for b in bb:
                    data.append(b)
        l = len(data) - 2
        data[1] = l
        s.sendall(data)


    def send_end(self, s):
        send = bytearray([3, 0])   # End
        s.sendall(send)


    def broadcast(self, msg:str):
        """Broadcasts a message to all the clients."""

        for sock in self.clients:
            sock.send(bytes(msg, "utf8"))

#######

