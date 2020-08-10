#!/usr/bin/python3
# -*- coding: future_fstrings -*-

"""
Fernschreiber IRC Client

requires python-fstrings
pip3 install future-fstrings


"""
__author__ = "TilCresonoator"
__email__ = "tilcreator@tc-j.de, benjamin.kunz@gmail.com"
__copyright__ = "CC 2019 TilCresonoator"
__license__ = "CC0"
__version__ = "0.0.0"


import ssl
import socket
import threading
import time
import queue

import logging
l = logging.getLogger("piTelex." + __name__)

import txDevITelexCommon
import txCode


class TelexIRC(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()

        self.directed_only = params.get('directed_only', False)

        self.running = True
        self.chars_buffer = ''
        self._is_online = False

        self.irc_client = IRC_Client(params.get("irc_server", "irc.nerd2nerd.org"), params.get("irc_port", 6697), params.get("irc_nick", "telextest"), params.get("irc_channel", "#tctesting"))

        self.thread = threading.Thread(target=self.thread_function, name='IRC_Handler')
        self.thread.start()


    def exit(self):
        self.irc_client.stop()
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

        if a not in "[]":
            self._tx_buffer.append(a)

    # =====

    def add_chars(self, chars):
        for char in chars:
            if char == '\r':
                continue
            if char == '\n':
                if self.chars_buffer.startswith('+'):
                    self.irc_client.send_msg(self.chars_buffer[1:], action=True)
                else:
                    self.irc_client.send_msg(self.chars_buffer)
                self.chars_buffer = ''
                continue
            self.chars_buffer += char


    def thread_function(self):
        """
            IRC client handler
        """
        last_date = None
        while self.running:
            try:
                data = self.irc_client.get_msg()
                if data is not None:
                    # TODO: wait for debian to catch up with real events
                    if data['type'] == 'PRIVMSG':
                        msg = f'={data["channel"][1:]} {data["nick"]}: {data["msg"]}'
                    if data['type'] == 'ACTION':
                        msg = f'={data["channel"][1:]} = {data["nick"]} {data["msg"]}'
                    if data['type'] == 'TOPIC':
                        msg = f'={data["channel"][1:]} TOPIC CHANGED by {data["nick"]}: {data["msg"]}'

                    if data['msg'].startswith(f'{self.irc_client.nick}:'):
                        msg = f'{msg}\a\a\a' # BEL

                    if data['msg'].startswith(f'{self.irc_client.nick}:') or not self.directed_only:
                        msg = f'{time.strftime("%H:%M", time.gmtime(data["timestamp"]))} {msg}\n\r'
                        if last_date != time.gmtime(data["timestamp"]).tm_yday:
                            msg = f'{time.strftime("%A %d %B", time.gmtime(data["timestamp"]))}\n\r {msg}'
                            last_date = time.gmtime(data["timestamp"]).tm_yday
                        text = txCode.BaudotMurrayCode.ascii_to_tty_text(msg)
                        # TODO: insert linebreak after 65 characters
                        for a in text:
                            self._rx_buffer.append(a)

                if self._tx_buffer:
                    a = self._tx_buffer.pop(0)
                    data = str(a.encode('ASCII'), 'utf8').lower()
                    self.add_chars(data)

            except socket.error:
                l.warning('ERROR socket', 2)
                break

        l.warning('end connection', 3)
        self._connected = False

#######

class IRC_Client():
    def __init__(self, server, port, nick, channel):
        self.irc = ssl.wrap_socket(socket.socket())

        self.q = queue.Queue()

        self.server = server
        self.port = port
        self.nick = nick
        self.channel = channel

        self.registered = False

        self.irc.connect((self.server, self.port))

        self.running = True
        self.thread = threading.Thread(target=self.thread_function, name='IRC_Client')
        self.thread.start()

        self._raw_send(f'USER {self.nick} 0 * :{self.nick}')
        self._raw_send(f'NICK {self.nick}')
        # TODO: handle auto nick append when nick in use
        while not self.registered:
            pass

        self._raw_send(f'JOIN {self.channel}')

    def _raw_send(self, data):
        l.debug(f'OUT: {data}')
        self.irc.send(bytes(f'{data}\r\n', 'utf-8'))

    def send_msg(self, msg, action=False):
        if action:
            msg = f'\x01ACTION {msg}\x01'
        self._raw_send(f'PRIVMSG {self.channel} :{msg}')

    def stop(self, quit_msg='Wah!'):
        self._raw_send(f'QUIT :{quit_msg}')
        self.running = False
        self.thread.join()
        self.irc.close()

        del self

    def get_msg(self):
        if self.q.empty():
            return None
        return self.q.get()

    def parse_irc_msg(self, line):
        split_ = line[1:].split(' ', 1)
        if line[0] == ':':
            source, line = (split_[0], split_[1])
        else:
            source, line = None, line
        split_ = line.split(' ', 1)
        command, line = (split_[0], None) if len(split_) == 1 else tuple(split_)
        if line is None:
            target = None
        else:
            split_ = line.split(' ', 1)
            target, line = (split_[0], None) if len(split_) == 1 else tuple(split_)
        if line is None:
            message = None
        else:
            message = line[1:] if line[0] == ':' else None
        if message is not None and message.startswith('\x01') and message.endswith('\x01'):
            message = message[8:-1]
            command = 'ACTION'
        if source is not None:
            nick = source.split('!')[0]
        else:
            nick = None
        return source, nick, command, target, message

    def thread_function(self):
        while self.running:
            data_raw = self.irc.recv(4096)
            data = str(data_raw, 'utf8', 'replace').replace('\n', '').split('\r')

            for line in data:
                if line == '':
                    continue

                l.debug(f'IN: {line}')

                if line.startswith('PING'):
                    self._raw_send(line.replace('PING', 'PONG', 1))
                    self.registered = True
                    continue

                source, nick, command, target, message = self.parse_irc_msg(line)
                if target == self.channel and command in ['PRIVMSG', 'TOPIC', 'ACTION']:
                    self.q.put({'type': command, 'user': source, 'nick': nick, 'channel': self.channel, 'msg': message, 'timestamp': time.time()})
                    continue
