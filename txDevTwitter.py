#!/usr/bin/python3
# -*- coding: future_fstrings -*-

"""
Fernschreiber Twitter Client

requires python-fstrings
pip3 install future-fstrings


"""
__author__ = "DirkNiggemann"
__email__ = "dirk.niggemann@gmail.com"
__copyright__ = "CC 2019 DirkNiggemann"
__license__ = "CC0"
__version__ = "0.0.0"


import threading
import time
import queue
import twitter
import json

import txDevITelexCommon
import txCode

import log


def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)


class TelexTwitter(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()
        self.running = True
        self.chars_buffer = ''
        self._is_online = False
        self.twitter_client = Twitter_Client(params.get("consumer_key", ""), params.get("consumer_secret", ""), params.get("access_token_key", ""), params.get("access_token_secret", ""), params.get("users", []))
        self.thread = threading.Thread(target=self.thread_function, name='Twitter_Handler')
        self.thread.start()


    def exit(self):
        self.twitter_client.stop()
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
                self.twitter_client.send_msg(self.chars_buffer)
                self.chars_buffer = ''
                continue
            self.chars_buffer += char


    def thread_function(self):
        """
            Twitter client handler
        """
        last_date = None
        while self.running:
            try:
                data = self.twitter_client.get_msg()
                if data is not None:
                    #if data['type'] == 'ACTION':
                    msg = f'={data["user"]["name"]} = {data["text"]}'
                    #if data['msg'].startswith(f'{self.irc_client.nick}:'):
                    #    msg = f'{msg}\a\a\a' # BEL
                    LOG(data["user"]["name"])

                    if '@' + data["user"]["name"] in self.twitter_client.users:
                        t =  time.strptime(data["created_at"], '%a %b %d %H:%M:%S %z %Y')
                        msg = f'{time.strftime("%H:%M", t)} {msg}\n\r'
                        if last_date != t.tm_yday:
                            msg = f'{time.strftime("%A %d %B", t)}\n\r {msg}'
                            last_date = t.tm_yday
                        text = txCode.BaudotMurrayCode.ascii_to_tty_text(msg)
                        # TODO: insert linebreak after 65 characters
                        for a in text:
                            self._rx_buffer.append(a)

                if self._tx_buffer:
                    a = self._tx_buffer.pop(0)
                    data = str(a.encode('ASCII'), 'utf8').lower()
                    self.add_chars(data)
            except twitter.error.TwitterError as e:
               LOG(str(e),1)

        LOG('end connection', 2)
        self._connected = False


#######

class Twitter_Client():
    LANGUAGES = ['en']
    def __init__(self, consumer_key, consumer_secret, access_token_key, access_token_secret, users):
        try:
           self.api = twitter.Api(consumer_key,
                  consumer_secret,
                  access_token_key,
                  access_token_secret,
                  sleep_on_rate_limit=True)
        except twitter.error.TwitterError as e:
           LOG(str(e),1)
        self.q = queue.Queue()
        self.users = users
        self.running = True
        self.thread = threading.Thread(target=self.thread_function, name='Twitter_Client')
        self.thread.start()



    def send_msg(self, msg):
        try:
           status = self.api.PostUpdate(msg)
        except UnicodeDecodeError:
           LOG("Your message could not be encoded.  Perhaps it contains non-ASCII characters? ",1)
           LOG("Try explicitly specifying the encoding with the --encoding flag",1)
        except twitter.error.TwitterError as e:
           LOG(str(e),1)

        LOG(f'TWEET: {msg}', 3)

    def stop(self, quit_msg='Wah!'):
        self.running = False
        self.thread.join()
        #self.api.close()

        del self

    def get_msg(self):
        if self.q.empty():
            return None
        return self.q.get()

    def thread_function(self):
        while self.running:
           try:
             self.idl = [ str(self.api.GetUser(screen_name=u).id) for u in self.users ]
             for line in self.api.GetStreamFilter(follow=self.idl, languages=Twitter_Client.LANGUAGES):
                if line == None:
                   continue
                LOG(f'IN: {json.dumps(line)}')
                self.q.put(line)
           except twitter.error.TwitterError as e:
              LOG(str(e), 1)
