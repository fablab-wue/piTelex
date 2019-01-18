#!/usr/bin/python
"""
Telex for connecting to i-Telex

    number = '97475'   # Werner
    number = '727272'   # DWD
    number = '234200'   # FabLabWue
    number = '91113'   #  www.fax-tester.de
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import socket
import time
from threading import Thread

import txCode
import txBase
import time

TNS_HOST = 'sonnibs.no-ip.org'  # The server's hostname or IP address    or itelex.teleprinter.net or 176.52.197.242
TNS_PORT = 11811        # The port used by the server

#######

def LOG(text:str):
    print('\033[5;30;46m<'+text+'>\033[0m', end='', flush=True)


class TelexITelexClient(txBase.TelexBase):
    def __init__(self, **params):

        super().__init__()

        self.id = '<'
        self.params = params

        #self._baudrate = params.get('baudrate', 50)
        #self._pin_txd = params.get('pin_txd', 17)
        #self._pin_rxd = params.get('pin_rxd', 27)
        #self._pin_dtr = params.get('pin_dtr', 22)
        #self._pin_rts = params.get('pin_rts', 10)
        #self._inv_rxd = params.get('pin_rxd', False)
        #self._inv_txd = params.get('pin_txd', False)
        self._tx_buffer = []
        self._rx_buffer = []
        self._connected = False
        self._received = 0

        #self.connect(number)
        

    def __del__(self):
        self._connected = False
        super().__del__()
    
    # =====

    def read(self) -> str:
        #if not self._tty.in_waiting:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bZ':   # end session
                self.disconnect_client()

            if a[:2] == '\x1b#':   # dial
                self.connect_client(a[2:])

            if a[:2] == '\x1b?':   # ask TNS
                tns = self.TNS(a[2:])
                print(tns)
            return

        if not self._connected:
            return

        self._tx_buffer.append(a)


    def idle(self):
        pass

    # =====

    def connect_client(self, number:str):
        Thread(target=self.thread_connect_as_client, args=(number.strip(),)).start()


    def disconnect_client(self):
        self._tx_buffer = []
        self._connected = False

    # =====

    def thread_connect_as_client(self, number):
        try:
            # get IP of given number from Telex-Number-Server (TNS)

            if number:
                lines = self.TNS(number)

                if len(lines) < 7 or lines[0] != 'ok':
                    self._rx_buffer.append('\x1bN')
                    raise Exception('No valid number')

                type = int(lines[3])
                host = lines[4]
                port = int(lines[5])
                dial = lines[6]
                is_ascii = (3 <= type <= 4)
            else:
                host = 'localhost'
                port = 2342
                dial = '-'
                is_ascii = False

            # connect to destination Telex

            mc = txCode.BaudotMurrayCode()
            mc.flip_bits = True

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                LOG('connected to '+lines[2])
                s.connect((host, port))
                s.settimeout(0.2)

                self._rx_buffer.append('\x1bA')
                self._connected = True

                if not is_ascii:
                    self.send_version(s)

                    if dial.isnumeric():
                        self.send_direct_dial(s, dial)

                while self._connected:
                    try:
                        data = s.recv(1)
                        
                        if not data:   # lost connection
                            break

                        elif data[0] <= 9:   # i-Telex packet
                            d = s.recv(1)
                            data += d
                            plen = d[0]
                            data += s.recv(plen)

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
                                self.send_ack(s)

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
                                if data[2] != 1:
                                    self.send_version(s)

                            elif data[0] == 8:   # Self test
                                LOG('Self test '+repr(data))
                                pass

                            elif data[0] == 9:   # Remote config
                                LOG('Remote config '+repr(data))
                                pass

                        else:   # ASCII character(s)
                            #LOG('Other', repr(data))
                            data = data.decode('ASCII', errors='ignore')
                            for a in data:
                                if a == '@':
                                    a = '#'
                                self._rx_buffer.append(a)

                    except socket.timeout:
                        #LOG('.')
                        if self._tx_buffer:
                            if is_ascii:
                                self.send_data_ascii(s)
                            else:
                                self.send_data_baudot(s, mc)


                    except socket.error:
                        LOG('Error socket')
                        break

                if not is_ascii:
                    self.send_end(s)
                LOG('end connection')

        except Exception as e:
            LOG(str(e))
            pass
        
        self._connected = False
        self._rx_buffer.append('\x1bZ')

    # =====

    def send_ack(self, s):
        data = bytearray([6, 1, self._received & 0xff])
        s.sendall(data)


    def send_version(self, s):
        send = bytearray([7, 1, 1])
        s.sendall(send)


    def send_direct_dial(self, s, dial):
        data = bytearray([1, 1])   # Direct Dial
        if len(dial) == 2:
            number = int(dial)
            if number == 0:
                number = 100
        elif len(dial) == 1:
            number = int(dial) + 100
            if number == 100:
                number = 110
        else:
            number = 0
        data.append(number)
        s.sendall(data)


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

    # =====

    @staticmethod
    def TNS(number):
        # get IP of given number from Telex-Number-Server (TNS)
        # typical answer: 'ok\r\n234200\r\nFabLab, Wuerzburg\r\n1\r\nfablab.dyn.nerd2nerd.org\r\n2342\r\n-\r\n+++\r\n'
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((TNS_HOST, TNS_PORT))
                qry = bytearray('q{}\r\n'.format(number), "ASCII")
                s.sendall(qry)
                data = s.recv(1024)

            data = data.decode('ASCII', errors='ignore')
            lines = data.split('\r\n')

            #LOG('Received from TNS '+repr(data))
            return lines

        except:
            return None

#######

