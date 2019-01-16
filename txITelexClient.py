#!/usr/bin/python
"""
Telex for connecting to i-Telex
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

        self._mc = txCode.BaudotMurrayCode()
        self._mc.flip_bits = True

        number = '97475'   # Werner
        number = '727272'   # DWD
        #number = '234200'   # FabLabWue
        number = '91113'   #  www.fax-tester.de

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
                self.disconnect()

            if a[:2] == '\x1b#':   # dial
                self.connect(a[2:])
            return

        if not self._connected:
            return

        self._tx_buffer.append(a)


    def idle(self):
        pass

    # =====

    def connect(self, number:str):
        self._number = number.strip()
        self._connected = True
        self._tx_thread = Thread(target=self.thread_client)
        self._tx_thread.start()


    def disconnect(self):
        self._tx_buffer = []
        self._connected = False


    def thread_client(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((TNS_HOST, TNS_PORT))
                qry = bytearray('q{}\r\n'.format(self._number), "ASCII")
                s.sendall(qry)
                data = s.recv(1024)

            data = data.decode('ASCII', errors='ignore')
            lines = data.split('\r\n')

            if len(lines) < 7 or lines[0] != 'ok':
                print('fail', repr(data))
                raise Exception('No valid number')

            type = int(lines[3])
            host = lines[4]
            port = int(lines[5])
            dial = lines[6]

            is_ascii = (3 <= type <= 4)

            print('Received', repr(data))



            #raise Exception('xxx')

            self._mc.reset()

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                s.settimeout(0.5)

                if not is_ascii:
                    qry = bytearray([7, 1, 1])
                    s.sendall(qry)

                while self._connected:
                    try:
                        data = s.recv(1024)
                        
                        if not data:   # lost connection
                            print('Error no data')
                            break
                        
                        elif data[0] == 0:   # Heartbeat
                            print('Heartbeat', repr(data))
                            pass

                        elif data[0] == 1:   # Direct Dial
                            print('Direct Dial', repr(data))
                            pass

                        elif data[0] == 2:   # Baudot data
                            print('Baudot data', repr(data))
                            l = len(data[2:])
                            aa = self._mc.decodeB2A(data[2:])
                            for a in aa:
                                if a == '@':
                                    a = '#'
                                self._rx_buffer.append(a)
                            self._received += l
                            send = bytearray([6, 1, self._received & 0xff])
                            s.sendall(send)

                        elif data[0] == 3:   # End
                            print('End', repr(data))
                            break

                        elif data[0] == 4:   # Reject
                            print('Reject', repr(data))
                            break

                        elif data[0] == 6:   # Acknowledge
                            print('Acknowledge', repr(data))
                            pass

                        elif data[0] == 7:   # Version
                            print('Version', repr(data))
                            if data[2] != 1:
                                send = bytearray([7, 1, 1])
                                s.sendall(send)

                        elif data[0] == 8:   # Self test
                            print('Self test', repr(data))
                            pass

                        elif data[0] == 9:   # Remote config
                            print('Remote config', repr(data))
                            pass

                        else:
                            #print('Other', repr(data))
                            data = data.decode('ASCII', errors='ignore')
                            for a in data:
                                if a == '@':
                                    a = '#'
                                self._rx_buffer.append(a)

                    except socket.timeout:
                        #print('Timeout')
                        #self.send_tx_buffer()
                        if self._tx_buffer:
                            if is_ascii:
                                a = self._tx_buffer.pop(0)
                                data = a.encode('ASCII')
                            else:
                                data = bytearray([2, 0])
                                while self._tx_buffer and len(data) < 100:
                                    a = self._tx_buffer.pop(0)
                                    bb = self._mc.encodeA2B(a)
                                    if bb:
                                        for b in bb:
                                            data.append(b)
                                l = len(data) - 2
                                data[1] = l
                            s.sendall(data)


                    except socket.error:
                        print('Error socket')
                        break

                if not is_ascii:
                    send = bytearray([3, 0])
                    s.sendall(send)
                print('end connection')

        except Exception as e:
            print(e)
            pass
        
        self._connected = False


    def send_tx_buffer(self):
        pass
#######

