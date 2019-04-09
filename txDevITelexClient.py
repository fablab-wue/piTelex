#!/usr/bin/python3
"""
Telex Device - i-Telex for connecting to other/external i-Telex stations

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

from threading import Thread
import socket
import time
import csv

import txCode
import txBase
import log

# TNS-servers:
# sonnibs.no-ip.org
# tlnserv.teleprinter.net
# tlnserv3.teleprinter.net
# telexgateway.de

#######

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)


class TelexITelexClient(txBase.TelexBase):
    USERLIST = []   # cached list of user dicts of file 'userlist.csv'
    _tns_host = ''
    _tns_port = 0
    _userlist = ''

    def __init__(self, **params):
        super().__init__()

        self.id = '>'
        self.params = params

        TelexITelexClient._tns_host = params.get('tns_host', 'sonnibs.no-ip.org')
        TelexITelexClient._tns_port = params.get('tns_port', 11811)
        TelexITelexClient._userlist = params.get('userlist', 'userlist.csv')

        self._tx_buffer = []
        self._rx_buffer = []
        self._connected = False


    def __del__(self):
        self.exit()
        super().__del__()


    def exit(self):
        self._connected = False

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bZ':   # end session
                self.disconnect_client()

            if a[:2] == '\x1b#':   # dial
                self.connect_client(a[2:])

            if a[:2] == '\x1b?':   # ask TNS
                number = a[2:]
                user = self.query_userlist(number)
                if not user:
                    user = self.query_TNS(number)
                if not user and number[0] == '0':
                    user = self.query_TNS(number[1:])
                print(user)
            return

        if source in '<>':
            return

        if not self._connected:
            return

        self._tx_buffer.append(a)
        #return True   #debug


    def idle(self):
        pass

    # =====

    def connect_client(self, number:str):
        Thread(target=self.thread_connect_as_client, name='iTelexC', args=(number.strip(),)).start()


    def disconnect_client(self):
        self._tx_buffer = []
        self._connected = False

    # =====

    def thread_connect_as_client(self, number):
        try:
            received = 0
            sent = 0
            timeout_counter = 5
            is_ping = True

            # get IP of given number from Telex-Number-Server (TNS)

            user = self.query_userlist(number)
            if not user:
                user = self.query_TNS(number)

            if not user and number[0] == '0':
                user = self.query_TNS(number[1:])

            if not user:
                return
                
            #self._rx_buffer.append('\x1bN')
            self._rx_buffer.append('\x1bA')

            is_ascii = user['Type'] == 'A'

            # connect to destination Telex

            bmc = txCode.BaudotMurrayCode(False, False, True)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                LOG('connected to '+user['Name'], 3)
                c = (user['Host'], int(user['Port']))
                s.connect(c)
                s.settimeout(0.2)

                self._connected = True

                if not is_ascii:
                    if user['ENum'].isnumeric():
                        self.send_direct_dial(s, user['ENum'])

                    self.send_version(s)

                while self._connected:
                    try:
                        data = s.recv(1)
                        
                        if not data:   # lost connection
                            break

                        elif data[0] < 10:   # i-Telex packet
                            d = s.recv(1)
                            data += d
                            plen = d[0]
                            if plen:
                                data += s.recv(plen)

                            if data[0] == 0:   # Heartbeat
                                #LOG('Heartbeat '+repr(data), 4)
                                pass

                            elif data[0] == 1:   # Direct Dial
                                LOG('Direct Dial '+repr(data), 4)
                                pass

                            elif data[0] == 2 and plen > 0:   # Baudot data
                                is_ping = False
                                #LOG('Baudot data '+repr(data), 4)
                                aa = bmc.decodeBM2A(data[2:])
                                for a in aa:
                                    if a == '@':
                                        a = '#'
                                    self._rx_buffer.append(a)
                                received += len(data[2:])
                                self.send_ack(s, received)

                            elif data[0] == 3:   # End
                                LOG('End '+repr(data), 4)
                                break

                            elif data[0] == 4:   # Reject
                                LOG('Reject '+repr(data), 4)
                                break

                            elif data[0] == 6 and plen == 1:   # Acknowledge
                                is_ping = False
                                #LOG('Acknowledge '+repr(data), 4)
                                LOG(str(data[2])+'/'+str(sent), 4)
                                pass

                            elif data[0] == 7 and plen >= 1:   # Version
                                LOG('Version '+repr(data), 4)
                                if data[2] != 1:
                                    self.send_version(s)
                                if user['ENum'].isnumeric():
                                    self.send_direct_dial(s, user['ENum'])

                            elif data[0] == 8:   # Self test
                                LOG('Self test '+repr(data), 4)
                                pass

                            elif data[0] == 9:   # Remote config
                                LOG('Remote config '+repr(data), 4)
                                pass

                        else:   # ASCII character(s)
                            is_ping = False
                            #LOG('Other', repr(data), 4)
                            data = data.decode('ASCII', errors='ignore').upper()
                            for a in data:
                                if a == '@':
                                    a = '#'
                                self._rx_buffer.append(a)
                                received += 1

                    except socket.timeout:
                        #LOG('.', 4)
                        timeout_counter -= 1
                        if timeout_counter <= 0:
                            timeout_counter = 3
                            #if not received and not is_ascii:
                            if is_ping:
                                self._tx_buffer.append('[')
                        else:
                            pass

                        if self._tx_buffer:
                            if is_ascii:
                                l = self.send_data_ascii(s)
                            else:
                                l = self.send_data_baudot(s, bmc)
                            sent += l


                    except socket.error:
                        LOG('Error socket', 2)
                        break

                if not is_ascii:
                    self.send_end(s)
                LOG('end connection', 3)

        except Exception as e:
            LOG(str(e))
            pass
        
        self._connected = False
        self._rx_buffer.append('\x1bZ')

    # =====

    def send_ack(self, s, received:int):
        data = bytearray([6, 1, received & 0xff])
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
        return len(data)


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
        return l


    def send_end(self, s):
        send = bytearray([3, 0])   # End
        s.sendall(send)

    # =====

    @classmethod
    def query_TNS(cls, number):
        # get IP of given number from Telex-Number-Server (TNS)
        # typical answer from TNS: 'ok\r\n234200\r\nFabLab, Wuerzburg\r\n1\r\nfablab.dyn.nerd2nerd.org\r\n2342\r\n-\r\n+++\r\n'
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((cls._tns_host, cls._tns_port))
                qry = bytearray('q{}\r\n'.format(number), "ASCII")
                s.sendall(qry)
                data = s.recv(1024)

            data = data.decode('ASCII', errors='ignore')
            items = data.split('\r\n')

            if len(items) >= 7 and items[0] == 'ok':
                if 3 <= int(items[3]) <= 4:
                    type = 'A'
                else:
                    type = 'I'
                user = {
                    'TNum': items[1],
                    'ENum': items[6],
                    'Name': items[2],
                    'Type': type,
                    'Host': items[4],
                    'Port': int(items[5]),
                }
                LOG('Found user in TNS '+str(user), 4)
                return user

        except:
            pass
            
        return None


    @classmethod
    def query_userlist(cls, number):
        # get IP of given number from CSV file
        # the header items must be: 'nick,tnum,extn,type,host,port,name' (can be in any order)
        # typical rows in csv-file: 'FABLAB, 234200, -, I, fablab.dyn.nerd2nerd.org, 2342, "FabLab, Wuerzburg"'
        try:
            if not TelexITelexClient.USERLIST:
                with open(cls._userlist, 'r') as f:
                    dialect = csv.Sniffer().sniff(f.read(1024))
                    f.seek(0)
                    csv_reader = csv.DictReader(f, dialect=dialect, skipinitialspace=True)
                    for user in csv_reader:
                        TelexITelexClient.USERLIST.append(dict(user))

            for user in TelexITelexClient.USERLIST:
                if number == user['Nick'] or number == user['TNum']:
                    LOG('Found user '+repr(user), 4)
                    return user

        except:
            pass

        return None

#######

