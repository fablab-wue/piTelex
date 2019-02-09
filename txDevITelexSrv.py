#!/usr/bin/python
"""
i-Telex Server
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

class TelexITelexSrv(txBase.TelexBase):
    def __init__(self, mode:str, **params):
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

        self.SERVER = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SERVER.bind(('', self._port))

        self.SERVER.listen(2)
        #print("Waiting for connection...")
        Thread(target=self.thread_srv_accept_incoming_connections).start()


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

        if source == '<' or source == '>':
            return

        self._tx_buffer.append(a)

    # =====

    def thread_srv_accept_incoming_connections(self):
        """Sets up handling for incoming clients."""
        while self.run:
            client, client_address = self.SERVER.accept()
            LOG("%s:%s has connected" % client_address, 3)
            if self.clients:   # one client is active!
                self.send_reject(client)
                client.close()
                continue
            self.clients[client] = client_address
            self._tx_buffer = []
            Thread(target=self.thread_srv_handle_client, args=(client,)).start()


    def thread_srv_handle_client(self, client):  # Takes client socket as argument.
        """Handles a single client connection."""
        bmc = txCode.BaudotMurrayCode(False, False, True)
        is_ascii = None   # not known yet

        client.settimeout(0.2)

        self._rx_buffer.append('\x1bA')

        while self.run:
            try:
                data = client.recv(1)
                
                if not data:   # lost connection
                    break

                elif data[0] < 0x10:   # i-Telex packet
                    if is_ascii is None:
                        self.send_welcome(client)
                    is_ascii = False
                    d = client.recv(1)
                    data += d
                    plen = d[0]
                    data += client.recv(plen)

                    if data[0] == 0:   # Heartbeat
                        #LOG('Heartbeat '+repr(data), 4)
                        pass

                    elif data[0] == 1:   # Direct Dial
                        LOG('Direct Dial '+repr(data), 4)
                        self._rx_buffer.append('\x1bD'+str(data[2]))

                    elif data[0] == 2 and plen > 0:   # Baudot data
                        #LOG('Baudot data '+repr(data), 4)
                        aa = bmc.decodeBM2A(data[2:])
                        for a in aa:
                            if a == '@':
                                a = '#'
                            self._rx_buffer.append(a)
                        self._received += len(data[2:])
                        self.send_ack(client)

                    elif data[0] == 3:   # End
                        LOG('End '+repr(data), 4)
                        break

                    elif data[0] == 4:   # Reject
                        LOG('Reject '+repr(data), 4)
                        break

                    elif data[0] == 6 and plen == 1:   # Acknowledge
                        #LOG('Acknowledge '+repr(data), 4)
                        LOG(str(data[2]))
                        pass

                    elif data[0] == 7 and plen >= 1:   # Version
                        #LOG('Version '+repr(data), 4)
                        self.send_version(client)

                    elif data[0] == 8:   # Self test
                        LOG('Self test '+repr(data), 4)
                        pass

                    elif data[0] == 9:   # Remote config
                        LOG('Remote config '+repr(data), 4)
                        pass

                else:   # ASCII character(s)
                    #LOG('Other', repr(data), 4)
                    if is_ascii is None:
                        self.send_welcome(client)
                    is_ascii = True
                    data = data.decode('ASCII', errors='ignore').upper()
                    data = txCode.BaudotMurrayCode.translate(data)
                    for a in data:
                        if a == '@':
                            a = '#'
                        self._rx_buffer.append(a)
                        self._received += 1


            except socket.timeout:
                #LOG('.', 4)
                if is_ascii is not None:
                    if self._tx_buffer:
                        if is_ascii:
                            self.send_data_ascii(client)
                        else:
                            self.send_data_baudot(client, bmc)
                    else:
                        if not is_ascii:
                            self.send_heartbeat(client)
                    

            except socket.error:
                LOG('Error socket', 2)
                break


        LOG('end connection', 3)
        client.close()
        del self.clients[client]
        self._rx_buffer.append('\x1bZ')
        pass


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


    def send_data_baudot(self, s, bmc):
        data = bytearray([2, 0])
        while self._tx_buffer and len(data) < 100:
            a = self._tx_buffer.pop(0)
            bb = bmc.encodeA2BM(a)
            if bb:
                for b in bb:
                    data.append(b)
        l = len(data) - 2
        data[1] = l
        s.sendall(data)


    def send_end(self, s):
        send = bytearray([3, 0])   # End
        s.sendall(send)


    def send_reject(self, s):
        send = bytearray([4, 3, 'o', 'c', 'c'])   # Reject
        s.sendall(send)


    def send_welcome(self, s):
        self._tx_buffer.extend(list('[[[\r\n'))   # send text
        self._rx_buffer.append('\x1bT')


    def broadcast(self, msg:str):
        """Broadcasts a message to all the clients."""

        for sock in self.clients:
            sock.send(bytes(msg, "utf8"))

#######

