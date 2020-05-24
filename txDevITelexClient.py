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
import datetime
import random
random.seed()

import txCode
import txBase
import log
import txDevITelexCommon

# List of TNS addresses as of 2020-04-21
# <https://telexforum.de/viewtopic.php?f=6&t=2504&p=17795#p17795>
tns_addresses = [
    "sonnibs.no-ip.org",
    "tlnserv.teleprinter.net",
    "tlnserv3.teleprinter.net",
    "telexgateway.de"
]

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

def choose_tns_address():
    """
    Return randomly chosen TNS (Telex number server) address, for load
    distribution.
    """
    return random.choice(tns_addresses)

def LOG(text:str, level:int=3):
    log.LOG('\033[30;46m<'+text+'>\033[0m', level)


class TelexITelexClient(txDevITelexCommon.TelexITelexCommon):
    USERLIST = []   # cached list of user dicts of file 'userlist.csv'
    _tns_port = 0
    _userlist = ''

    def __init__(self, **params):
        super().__init__()

        self.id = '>'
        self.params = params

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

            number = number.replace('[', '')
            number = number.replace(']', '')
            number = number.replace(' ', '')

            if len(number) < 2:
                return

            user = cls.query_userlist(number)

            if not user:
                user = cls.query_TNS_bin(number)

            if not user and number[0] == '0':
                user = cls.query_TNS_bin(number[1:])

            return user

    @classmethod
    def query_TNS_bin(cls, number):
        """
        Query TNS for member contact information (hostname/ip address, port) by
        telex number

        For details, see implementation and i-Telex Communication Specification
        (r874).
        """
        try:
            # Sanitise subscriber number so it will fit the Peer_query
            number = int(number)
            if number < 0 or number > 0xffffffff:
                raise ValueError("Invalid subscriber number")
            number = number.to_bytes(length=4, byteorder="little")

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((choose_tns_address(), cls._tns_port))
                # Peer_query packet:
                #                Code  Len
                qry = bytearray([0x03, 0x05])
                # Number
                qry.extend(number)
                # Version
                qry.append(0x01)
                s.sendall(qry)
                data = s.recv(1024)
                s.close()
            if data[0] == 0x04: # Peer_not_found
                return None
            elif data[0] == 0x05: # Peer_reply_v1
                if not data[1] == 0x64:
                    raise ValueError("Peer_reply_v1 should have length 0x64, bus has 0x{0:x} instead".format(data[1]))
                # telex number of entry
                number_recv = str(int.from_bytes(data[2:6], byteorder="little", signed=False))
                # name of entry holder
                name = data[6:46].decode("ISO8859-1").rstrip('\x00')
                # flags, ignored as per spec
                flags = data[46:48]
                # entry type; see below
                entry_type_raw = data[48]
                # hostname
                hostname = data[49:89].decode("ISO8859-1").rstrip('\x00')
                # IP address
                ip_address = ".".join([str(i) for i in data[89:93]])
                # TCP port
                port = int.from_bytes(data[93:95], byteorder="little", signed=False)
                # local dialling extension
                extension = data[95]
                # No real requirement, just to get equal results compared with
                # text protocol. As per the specs, the text protocol should
                # send "0" on no extension, but it sends a dash instead.
                if extension == 0:
                    extension = '-'
                # PIN: ignored as per spec
                pin = data[96:98]
                # last changed date: caution, UTC! ignored as of now.
                date_secs_since_itx_epoch = int.from_bytes(data[98:], byteorder="little", signed=False)
                date = itx_epoch + datetime.timedelta(seconds=date_secs_since_itx_epoch)

                if entry_type_raw in [1, 2, 5]:
                    # Baudot type
                    entry_type = 'I'
                elif entry_type_raw in [3, 4]:
                    # ASCII type
                    entry_type = 'A'
                else:
                    # non-supported type (0: deleted; 6: e-mail)
                    return None

                if entry_type_raw in [1, 3]:
                    # fixed hostname given
                    host = hostname
                else:
                    # IP address given
                    host = ip_address

                user = {
                    'TNum': number_recv,
                    'ENum': extension,
                    'Name': name,
                    'Type': entry_type,
                    'Host': host,
                    'Port': port
                }
                LOG('Found user in TNS '+str(user), 4)
                return user

        except Exception as e:
            LOG(str(e))
            return None

    @classmethod
    def query_TNS(cls, number):
        # get IP of given number from Telex-Number-Server (TNS)
        # typical answer from TNS: 'ok\r\n234200\r\nFabLab, Wuerzburg\r\n1\r\nfablab.dyn.nerd2nerd.org\r\n2342\r\n-\r\n+++\r\n'
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((choose_tns_address(), cls._tns_port))
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

