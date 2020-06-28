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
import txDevITelexCommon

# TNS-servers:
# sonnibs.no-ip.org
# tlnserv.teleprinter.net
# tlnserv3.teleprinter.net
# telexgateway.de

#######

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)


class TelexITelexClient(txDevITelexCommon.TelexITelexCommon):
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


    def exit(self):
        self.disconnect_client()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bZ':   # end session
                self.disconnect_client()

            if a[:2] == '\x1b#':   # dial
                user = self.get_user(a[2:])
                if user:
                    self.connect_client(user)

            if a[:2] == '\x1b?':   # ask TNS
                user = self.get_user(a[2:])
                print(user)
            return

        if source in '<>':
            return

        #if not self._connected:
        #    return

        self._tx_buffer.append(a)
        #return True   #debug


    def idle(self):
        pass

    # =====

    def connect_client(self, user):
        Thread(target=self.thread_connect_as_client, name='iTelexC', args=(user,)).start()

    # =====

    def thread_connect_as_client(self, user):
        try:
            # get IP of given number from Telex-Number-Server (TNS)
                
            is_ascii = user['Type'] in 'Aa'

            # connect to destination Telex

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                address = (user['Host'], int(user['Port']))
                s.connect(address)
                LOG('connected to '+user['Name'], 3)

                self._rx_buffer.append('\x1bA')

                if not is_ascii:
                    self.send_version(s)
                    self.send_direct_dial(s, user['ENum'], 0)

                self.process_connection(s, False, is_ascii)

        except Exception as e:
            LOG(str(e))
            self.disconnect_client()
        
        s.close()
        self._rx_buffer.append('\x1bZ')

    # =====

    @classmethod
    def get_user(cls, number:str):

            number = number.replace('<', '')
            number = number.replace('>', '')
            number = number.replace(' ', '')

            if len(number) < 2:
                return

            user = cls.query_userlist(number)
            
            if not user:
                user = cls.query_TNS(number)

            if not user and number[0] == '0':
                user = cls.query_TNS(number[1:])

            return user


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
        # typical rows in csv-file: 'FABLABWUE, 234200, -, I, fablab.dyn.nerd2nerd.org, 2342, "FabLab, Wuerzburg"'
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

