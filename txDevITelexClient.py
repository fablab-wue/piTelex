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
import sys

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import txDevITelexCommon
from txDevITelexCommon import ST


class TelexITelexClient(txDevITelexCommon.TelexITelexCommon):
    USERLIST = []   # cached list of user dicts of file 'userlist.csv'
    _tns_port = 0
    _userlist = ''

    def __init__(self, **params):
        super().__init__()

        self.id = 'iTc'
        self.params = params

        TelexITelexClient._tns_addresses = params.get('tns_srv', ['tlnserv.teleprinter.net','tlnserv2.teleprinter.net','tlnserv3.teleprinter.net'])
        # print('TNS: ',TelexITelexClient._tns_addresses)
        TelexITelexClient._tns_port = params.get('tns_port', 11811)
        TelexITelexClient._userlist = params.get('userlist', 'userlist.csv')


    def exit(self):
        self.disconnect_client()
        self._run = False

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            l.debug("read: {!r}".format(self._rx_buffer[0]))
            return self._rx_buffer.pop(0)


    def write(self, a:str, source:str):
        super().write(a, source)
        l.debug("write from {!r}: {!r}".format(source, a))
        if len(a) != 1:
            if a == '\x1bZ':   # end session
                self.disconnect_client()

            if a[:2] == '\x1b#':   # dial
                try:
                    instant_dial = (a[2] == '!')
                except IndexError:
                    instant_dial = False
                if instant_dial:
                    # Instant dial: Fail silently if number not found
                    user = self.get_user(a[3:])
                    if user:
                        self.connect_client(user)
                else:
                    # Normal dial: Fail loudly if number not found
                    user = self.get_user(a[2:])
                    if user:
                        self.connect_client(user)
                    else:
                        self._rx_buffer.append('\x1bA')
                        self._rx_buffer.extend('bk')
                        self._rx_buffer.append('\x1bZ')


            if a[:2] == '\x1b?':   # ask TNS
                user = self.get_user(a[2:], tns_force = True)
                print(user)
            return

        if source in ['iTc', 'iTs']:
            return

        if self._connected <= ST.DISCON:
            return

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
            l.info('connecting to {Name} ({Host}:{Port})'.format(**user))

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                address = (user['Host'], int(user['Port']))
                s.settimeout(5.0) # Wait at most 5 s during connect
                try:
                    # Catch all errors during connect here to print proper
                    # error message
                    s.connect(address)
                except OSError as e:
                    # Error during connect: print error and switch off printer
                    self._rx_buffer.append('\x1bA')
                    self._rx_buffer.extend('nc')
                    l.warning("Could not connect: {!s}".format(e))
                    self.disconnect_client()
                else:
                    s.settimeout(None) # Re-enable blocking mode

                    if not is_ascii:
                        self.send_version(s)
                        self.send_direct_dial(s, user['ENum'])
                    l.info("connected")
                    self.process_connection(s, False, is_ascii)

        except Exception:
            l.error("Exception caught:", exc_info = sys.exc_info())
            self.disconnect_client()

        s.close()

#        self._rx_buffer.append('\x1bZ') # rowo 
        self._rx_buffer.append('\x1bST') # rowo don't force Z mode (would wake up from ZZ...), but trigger transit to sleep
        self._printer_running = False

    # =====

    @classmethod
    def get_user(cls, number:str, tns_force:bool = False):
        # For details about dialling logic, see txDevMCP in thread_dial.
        number = number.replace('<', '')
        number = number.replace('>', '')
        number = number.replace(' ', '')
        l.info("Get User: {!r}".format(number))

        # Direct Dial override: Dial <number>-<ddext> to have the direct dial
        # extension from TNS replaced by the dialled extension.
        number, _, ddext = number.partition("-")

        if len(number) < 1:
            l.warning("Number too short {!r}".format(number))
            return None

        # Query locally
        user = cls.query_userlist(number)

        # With at least 5 digits, also query remotely
        if not user and (len(number) >= 5 or tns_force):
            user = cls.query_TNS_bin(number)

            # Also accept leading zero for compatibility reasons
            if not user and number[0] == '0':
                user = cls.query_TNS_bin(number[1:])

        # Direct dial override continued
        if user and ddext:
            if ddext.isnumeric() and 1 <= len(ddext) <= 2:
                l.info("Direct dial override: {!r}".format(ddext))
                user['ENum'] = ddext
            else:
                l.warning("Invalid direct dial override, ignored: {!r}".format(ddext))

        if not user:
            l.info("No user found for number {!r}".format(number))
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
                s.connect((cls.choose_tns_address(), cls._tns_port))
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
                extension = txDevITelexCommon.decode_ext_from_direct_dial(data[95])
                # PIN: ignored as per spec
                pin = data[96:98]
                # last changed date: caution, UTC! ignored as of now.
                date_secs_since_itx_epoch = int.from_bytes(data[98:], byteorder="little", signed=False)
                date = cls.itx_epoch + datetime.timedelta(seconds=date_secs_since_itx_epoch)

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
                l.info('Found user in TNS: '+str(user))
                return user

        except Exception:
            l.error("Exception caught:", exc_info = sys.exc_info())
            return None

    @classmethod
    def query_TNS(cls, number):
        # get IP of given number from Telex-Number-Server (TNS)
        # typical answer from TNS: 'ok\r\n234200\r\nFabLab, Wuerzburg\r\n1\r\nfablab.dyn.nerd2nerd.org\r\n2342\r\n-\r\n+++\r\n'
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((cls.choose_tns_address(), cls._tns_port))
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
                l.info('Found user in TNS: '+str(user))
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
                    l.info('Found user in local userlist: '+repr(user))
                    return user

        except:
            pass

        return None

#######

