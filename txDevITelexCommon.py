#!/usr/bin/python3
"""
Telex Device - i-Telex Common Routines in Client and Server
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread
import socket
import time
import datetime
import random
random.seed()

import txCode
import txBase
import log

#######

def LOG(text:str, level:int=3):
    log.LOG('\033[30;44m<'+text+'>\033[0m', level)

class TelexITelexCommon(txBase.TelexBase):
    def __init__(self):
        super().__init__()

        self._rx_buffer = []
        self._tx_buffer = []
        self._connected = False


    def __del__(self):
        self.exit()
        super().__del__()
    

    def exit(self):
        self._connected = False

    # =====

    def disconnect_client(self):
        self._tx_buffer = []
        self._connected = False

    # =====

    def process_connection(self, s:socket.socket, is_server:bool, is_ascii:bool):  # Takes client socket as argument.
        """Handles a client or server connection."""
        bmc = txCode.BaudotMurrayCode(False, False, True)
        sent_counter = 0
        received_counter = 0
        timeout_counter = -1
        time_next_send = None

        s.settimeout(0.2)

        self._connected = True

        while self._connected:
            try:
                data = s.recv(1)
                
                # lost connection
                if not data:
                    break

                # Telnet control sequence
                elif data[0] == 255:
                    d = s.recv(2)   # skip next 2 bytes from telnet command

                # i-Telex packet
                elif data[0] < 10:
                    packet_error = False

                    d = s.recv(1)
                    data += d
                    packet_len = d[0]
                    if packet_len:
                        data += s.recv(packet_len)

                    # Heartbeat
                    if data[0] == 0 and packet_len == 0:
                        #LOG('Heartbeat '+repr(data), 4)
                        pass

                    # Direct Dial
                    elif data[0] == 1 and (1 <= packet_len <= 10):
                        LOG('Direct Dial '+repr(data), 4)
                        if packet_len >= 5:
                            id = (data[3] << 24) | (data[4] << 16) | (data[5] << 8) | (data[6])
                            print(id)
                        self._rx_buffer.append('\x1bD'+str(data[2]))
                        self.send_ack(s, received_counter)

                    # Baudot Data
                    elif data[0] == 2 and packet_len >= 1 and packet_len <= 50:
                        #LOG('Baudot data '+repr(data), 4)
                        aa = bmc.decodeBM2A(data[2:])
                        for a in aa:
                            if a == '@':
                                a = '#'
                            self._rx_buffer.append(a)
                        received_counter += len(data[2:])
                        self.send_ack(s, received_counter)

                    # End
                    elif data[0] == 3 and packet_len == 0:
                        LOG('End '+repr(data), 4)
                        break

                    # Reject
                    elif data[0] == 4 and packet_len <= 20:
                        LOG('Reject '+repr(data), 4)
                        aa = bmc.translate(data[2:])
                        for a in aa:
                            self._rx_buffer.append(a)
                        break

                    # Acknowledge
                    elif data[0] == 6 and packet_len == 1:
                        #LOG('Acknowledge '+repr(data), 4)
                        unprinted = (sent_counter - int(data[2])) & 0xFF
                        #if unprinted < 0:
                        #    unprinted += 256
                        LOG(str(data[2])+'/'+str(sent_counter)+'='+str(unprinted), 4)
                        if unprinted < 7:   # about 1 sec
                            time_next_send = None
                        else:
                            time_next_send = time.time() + (unprinted-6)*0.15
                        pass

                    # Version
                    elif data[0] == 7 and packet_len >= 1 and packet_len <= 20:
                        #LOG('Version '+repr(data), 4)
                        if not is_server or data[2] != 1:
                            self.send_version(s)

                    # Self test
                    elif data[0] == 8 and packet_len >= 2:
                        LOG('Self test '+repr(data), 4)
                        pass

                    # Remote config
                    elif data[0] == 9 and packet_len >= 3:
                        LOG('Remote config '+repr(data), 4)
                        pass

                    # Wrong packet - will resync at next socket.timeout
                    else:
                        LOG('ERROR Packet '+repr(data), 3)
                        packet_error = True

                    if not packet_error:
                        is_ascii = False


                # ASCII character(s)
                else:
                    #LOG('Other', repr(data), 4)
                    is_ascii = True
                    data = data.decode('ASCII', errors='ignore').upper()
                    data = txCode.BaudotMurrayCode.translate(data)
                    for a in data:
                        if a == '@':
                            a = '#'
                        self._rx_buffer.append(a)
                        received_counter += 1


            except socket.timeout:
                #LOG('.', 4)
                if is_ascii is not None:   # unknown if ASCII or baudot
                    timeout_counter += 1
                    if is_server and timeout_counter == 1:
                        self._tx_buffer = []
                        self.send_welcome(s)
                    
                    if is_ascii:
                        if self._tx_buffer:
                            sent = self.send_data_ascii(s)
                            sent_counter += sent

                    else:   # baudot
                        if (timeout_counter % 5) == 0:   # every 1 sec
                            self.send_ack(s, received_counter)

                        if self._tx_buffer:
                            if time_next_send and time.time() < time_next_send:
                                LOG('Wait'+str(int(time_next_send-time.time())), 4)
                                pass
                            else:
                                sent = self.send_data_baudot(s, bmc)
                                sent_counter += sent
                                if sent > 7:
                                    time_next_send = time.time() + (sent-6)*0.15
                        
                        elif (timeout_counter % 15) == 0:   # every 3 sec
                            self.send_heartbeat(s)
                    

            except socket.error:
                LOG('ERROR socket', 2)
                break


        if not is_ascii:
            self.send_end(s)
        LOG('end connection', 3)
        self._connected = False


    def send_heartbeat(self, s):
        '''Send heartbeat packet (0)'''
        data = bytearray([0, 0])
        s.sendall(data)


    def send_ack(self, s, received:int):
        '''Send acknowlage packet (6)'''
        data = bytearray([6, 1, received & 0xff])
        s.sendall(data)


    def send_version(self, s):
        '''Send version packet (7)'''
        send = bytearray([7, 1, 1])
        s.sendall(send)


    def send_direct_dial(self, s, dial:str, id):
        '''Send direct dial packet (1)'''
        data = bytearray([1, 5])   # Direct Dial
        if not dial.isnumeric():
            number = 0
        elif len(dial) == 2:
            number = int(dial)
            if number == 0:
                number = 100
        elif len(dial) == 1:
            number = int(dial) + 100
            if number == 100:
                number = 110
        else:
            number = 0
        data.append(number)   # direct dial number
        data.append(1)    # id, 32 bit
        data.append(2)
        data.append(3)
        data.append(4)
        s.sendall(data)


    def send_data_ascii(self, s):
        '''Send ASCII data direct'''
        a = ''
        while self._tx_buffer and len(a) < 250:
            b = self._tx_buffer.pop(0)
            if b not in '[]~%':
                a += b
        data = a.encode('ASCII')
        s.sendall(data)
        return len(data)


    def send_data_baudot(self, s, bmc):
        '''Send baudot data packet (2)'''
        data = bytearray([2, 0])
        while self._tx_buffer and len(data) < 42:
            a = self._tx_buffer.pop(0)
            bb = bmc.encodeA2BM(a)
            if bb:
                for b in bb:
                    data.append(b)
        l = len(data) - 2
        data[1] = l
        s.sendall(data)
        return l


    def send_end(self, s):
        '''Send end packet (3)'''
        send = bytearray([3, 0])   # End
        s.sendall(send)


    def send_reject(self, s):
        '''Send reject packet (4)'''
        send = bytearray([4, 3, ord('o'), ord('c'), ord('c')])   # Reject
        s.sendall(send)


    def send_welcome(self, s):
        '''Send welcome message indirect as a server'''
        #self._tx_buffer.extend(list('[[[\r\n'))   # send text
        #self._rx_buffer.append('\x1bT')
        #self._rx_buffer.append('#')
        #self._rx_buffer.append('@')
        self._rx_buffer.append('\x1bI')

    # i-Telex epoch has been defined as 1900-01-00 00:00:00 (sic)
    # What's probably meant is          1900-01-01 00:00:00
    # Even more probable is UTC, because naive evaluation during a trial gave a 2 h
    # offset during CEST. If needed, this must be expanded for local timezone
    # evaluation.
    itx_epoch = datetime.datetime(
        year = 1900,
        month = 1,
        day = 1,
        hour = 0,
        minute = 0,
        second = 0
    )

    # List of TNS addresses as of 2020-04-21
    # <https://telexforum.de/viewtopic.php?f=6&t=2504&p=17795#p17795>
    _tns_addresses = [
        "sonnibs.no-ip.org",
        "tlnserv.teleprinter.net",
        "tlnserv3.teleprinter.net",
        "telexgateway.de"
    ]

    @classmethod
    def choose_tns_address(cls):
        """
        Return randomly chosen TNS (Telex number server) address, for load
        distribution.
        """
        return random.choice(cls._tns_addresses)



#######

