#!/usr/bin/python3
# -*- coding: future_fstrings -*-

"""
Simple Telex Twitter Client that doesn't need a listener

requires python-fstrings
pip3 install future-fstrings

To turn this module on add the following to the devices section of the configuration

    "twitterV2" : {
      "type" : "twitterV2",
      "enable" : true,
      "consumer_key" : "kdeueniuaeiceyiueycw",
      "consumer_secret" : "fahlvuaeuwcniinn",
      "access_token" : "fahlvuaeuwcniinn",
      "access_token_secret" : "fahlvuaeuwcniinn",
      "bearer_token" : "fahlvuaeuwcniinn",
      "user_mentions": "mch2022telex" 
    }

This article shows you how to get these credentials, make sure you give your app 'write' rights as well
if you want to tweet from your telex
https://www.jcchouinard.com/twitter-api-credentials/

user_mentions is the user account that you want to print the mentions of.

"""
__author__ = "Frank BreBreedijk"
__license__ = "CC0"
__version__ = "0.0.1"


import threading
import time
import datetime
import queue
import tweepy

import json

import txDevITelexCommon
import txCode

import log
import logging

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)


class TelexTwitterV2(txDevITelexCommon.TelexITelexCommon):
    def __init__(self, **params):
        super().__init__()
        self.id = 'TwtV2'
        self.running = True
        self.chars_buffer = ''
        self._is_online = False
        self.twitter_client = Twitter_Client_V2(
            params.get("consumer_key", ""), 
            params.get("consumer_secret", ""), 
            params.get("access_token", ""), 
            params.get("access_token_secret", ""), 
            params.get("bearer_token", ""),  
            params.get("user_mentions", "")
        )
        self.thread = threading.Thread(target=self.thread_function, name='Twitter_Handler_V2')
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

        if a not in "<>":
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
        while self.running:
            try:
                data = self.twitter_client.get_msg()
                if data is not None:
                    lines = str(data['tweet']).split("\n")
                    out_lines = []
                    for line in lines:
                        if len(line) > 65:
                            out_lines.append(line[0:64])
                            line = line[65:]
                            while len(line) > 65 :
                                out_lines.append(line[0:64])
                                line = line[65:]
                        out_lines.append(line)
                    tweet_txt_out = "\r\n\r".join(out_lines)

                    msg = "\r---\r\n\r{}\r\n\r{} (@{})\r\n\r{}\r\r\n---\r\n\r\n\r".format(
                          tweet_txt_out,
                          data['user']['name'],
                          data['user']['username'],
                          data['tweet']["created_at"]
                    )
                    msg = msg.replace("@", "(A)")

                    text = txCode.BaudotMurrayCode.ascii_to_tty_text(msg)
                    for a in text:
                        self._rx_buffer.append(a)

                if self._tx_buffer:
                    a = self._tx_buffer.pop(0)
                    data = str(a.encode('ASCII'), 'utf8').lower()
                    self.add_chars(data)
            except Exception as e:
               LOG("txDevTwitterV2.thread_function: {}".format(str(e)),1)

        LOG('end connection', 2)
        self._connected = False


#######
class Twitter_Client_V2():

   def __init__(self, consumer_key, consumer_secret, access_token, access_token_secret, bearer_token, user_mentions):
        try:
            self.client = tweepy.Client(
                consumer_key        = consumer_key,
                consumer_secret     = consumer_secret,
                access_token        = access_token, 
                access_token_secret = access_token_secret,
                bearer_token        = bearer_token
            )
        except tweepy.error.TweepyException as e:
           LOG("Twitter login error:",1)
           LOG(str(e),1)
        self.user_mentions = "{}".format(user_mentions)
        self.last_id = 0
        self.q = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self.thread_function, name='Twitter_Client_V2')
        self.thread.start()
        print ("End of _init_")



   def send_msg(self, msg):
        try:
            msg = msg.replace("(a)", "@")
            status = self.client.create_tweet( text=msg, user_auth=True )
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
        users = {}
        if self.user_mentions :
            while self.running:
                try:
                    if self.last_id == 0 :
                        max_results = 5
                    else :
                        max_results = None
                    user = self.client.get_user(username=self.user_mentions)
                    LOG("User:",1)
                    LOG(str(user),1)
                    mentions = self.client.get_users_mentions(
                        id=user[0]["id"],
                        tweet_fields=["author_id","created_at"],
                        user_fields=["id","username"],
                        expansions=["author_id"],
                        since_id=self.last_id,
                        max_results=max_results
                    )
                    if mentions.data is not None:
                        users = {}
                        if self.last_id == 0:
                            tweets = mentions.data[:3]
                            tweets = tweets[::-1]
                        else:
                            tweets = mentions.data[::-1]

                        # Extract user data first
                        for u in mentions[1]['users']:
                            users[u['id']] = u
                        for tweet in tweets:
                            user_tweet = {
                                "tweet" : tweet,
                                "user" : users[tweet["author_id"]]
                            }
                            self.q.put(user_tweet)
                            self.last_id=tweet['id']
                except tweepy.TweepyException as e:
                    LOG("Twitter mentions error:", 1)
                    LOG(str(e), 1)
                time.sleep(15)
        else:
            # Do nothing
            while self.running:
                time.sleep(10000000)
