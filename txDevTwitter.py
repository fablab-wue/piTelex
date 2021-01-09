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
import datetime
import queue
import tweepy
from twitivity import Event

import json

import txDevITelexCommon
import txCode

import log
import logging

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)


class TelexTwitter(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()
        self.running = True
        self.chars_buffer = ''
        self._is_online = False
        self.twitter_client = Twitter_Client(params.get("consumer_key", ""), params.get("consumer_secret", ""), params.get("access_token_key", ""), params.get("access_token_secret", ""), params.get("follow", []),  params.get("track", []), params.get("languages", []), params.get("url", []), params.get("host", []), params.get("port", []))
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
                    if isinstance(data, dict):
                       #LOG(json.dumps(data), 1)
                       events = data['tweet_create_events']
                       uname =  events[0]['user']['screen_name']
                       ctime = datetime.datetime.strptime(events[0]['created_at'], '%a %b %d %H:%M:%S %z %Y')
                       txt = events[0]['text']
                    else:
                       uname = data.user.screen_name
                       ctime = data.created_at
                       txt = data.text
                    #if data['type'] == 'ACTION':
                    msg = f'={uname} = {txt}'
                    #if data['msg'].startswith(f'{self.irc_client.nick}:'):
                    #    msg = f'{msg}\a\a\a' # BEL
                    LOG(uname)

                    if '@' + uname in self.twitter_client.follow or not self.twitter_client.follow:
                        msg = f'{ctime.strftime("%H:%M")} {msg}\n\r'
                        if last_date != ctime.timetuple().tm_yday:
                            msg = f'{ctime.strftime("%A %d %B")}\n\r {msg}'
                            last_date = ctime.timetuple().tm_yday
                        text = txCode.BaudotMurrayCode.ascii_to_tty_text(msg)
                        # TODO: insert linebreak after 65 characters
                        for a in text:
                            self._rx_buffer.append(a)

                if self._tx_buffer:
                    a = self._tx_buffer.pop(0)
                    data = str(a.encode('ASCII'), 'utf8').lower()
                    self.add_chars(data)
            except Exception as e:
               LOG(str(e),1)

        LOG('end connection', 2)
        self._connected = False


#######
class Twitter_Client():
   class UserStreamListener(tweepy.StreamListener):
       def __init__(self, client):
          super().__init__()
          self.client = client
       def on_status(self, status):
          LOG(f'IN: {status}', 3)
          self.client.q.put(status)

   class ActivityStreamEvent(Event):
      CALLBACK_URL: str = "https://telex.mupptastic.org.uk:4330/listener"

      def __init__(self, client, url):
        super().__init__() 
        self.client = client
        self.CALLBACK_URL = url

      def on_data(self, data: json) -> None:
          LOG(f'IN: {data}', 3)
          self.client.q.put(data)

   LANGUAGES = ['en']
   def __init__(self, consumer_key, consumer_secret, access_token_key, access_token_secret, follow, track, languages, url, host, port):
        try:
           self.auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
           self.auth.set_access_token(
                  access_token_key,
                  access_token_secret)
           self.api = tweepy.API(self.auth)
        except tweepy.error.TweepError as e:
           LOG(str(e),1)
        self.q = queue.Queue()
        self.follow = follow
        self.track = track
        self.languages = languages
        self.url = url
        self.host = host
        self.port = port
        self.running = True
        self.thread = threading.Thread(target=self.thread_function, name='Twitter_Client')
        self.thread.start()



   def send_msg(self, msg):
        try:
           status = self.api.update_status(msg)
        except UnicodeDecodeError:
           LOG("Your message could not be encoded.  Perhaps it contains non-ASCII characters? ",1)
           LOG("Try explicitly specifying the encoding with the --encoding flag",1)
        except tweepy.error.TweepError as e:
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
             if self.follow:
               self.idl = [ str(self.api.get_user(screen_name=u).id) for u in self.follow ]
               self.listener = Twitter_Client.UserStreamListener(self) 
               self.stream = tweepy.Stream(auth=self.api.auth, listener=self.listener)
               self.stream.filter(follow=self.idl, track=self.track)
               time.sleep(10000000)
             else:
               stream_events = Twitter_Client.ActivityStreamEvent(self, self.url)
               stream_events._server.run(debug=False, ssl_context='adhoc', host=self.host, port = self.port)
               time.sleep(1)
           except tweepy.error.TweepError as e:
              LOG(str(e), 1)
