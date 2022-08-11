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

access_toeken and access_token_secret need to be generated separetely.

user_mentions is the user account that you want to print the mentions of.

"""
__author__ = "Frank BreBreedijk"
__license__ = "CC0"
__version__ = "0.5.0"


import threading
import time
import datetime
import queue
import tweepy

import json

import txBase
import txCode

import log
import logging
import html

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)




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
        except tweepy.error.TweepError as e:
           LOG(str(e),1)
        self.user_mentions = "{}".format(user_mentions)
        self.last_id = 0
        self.q = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self.thread_function, name='Twitter_Client_V2')
        self.thread.start()



   def send_msg(self, msg):
        try:
            msg = msg.replace("(a)", "@")
            msg = msg.replace("(hash)", "#")
            status = self.client.create_tweet( text=msg, user_auth=True )
        except UnicodeDecodeError:
           LOG("Your message could not be encoded.  Perhaps it contains non-ASCII characters? ",1)
           LOG("Try explicitly specifying the encoding with the --encoding flag",1)
        except tweepy.error.TweepError as e:
           LOG(str(e),1)

        LOG(f'TWEETING: {msg}', 3)

   def stop(self, quit_msg='Wah!'):
        self.running = False
        self.thread.join()
        #self.api.close()

        del self


   def thread_function(self):
        users = {}
        while self.running:
            if self.user_mentions :
                try:
                    if self.last_id == 0 :
                        max_results = 5
                    else :
                        max_results = None
                    user = self.client.get_user(username=self.user_mentions)
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
                            txt = str(tweet)
                            txt = txt.replace("&lt;","<")
                            txt = txt.replace("&gt;",">")
                            txt = txt.replace("&amp;","&")
                            user_tweet = {
                                "tweet" : tweet,
                                "escaped" : txt,
                                "user" : users[tweet["author_id"]]
                            }
                            #LOG(f'TWEET FROM: {user_tweet['user']}', 3)
                            LOG(f'TWEET: {txt}', 3)
                            self.q.put(user_tweet)
                            self.last_id=tweet['id']
                except tweepy.TweepError as e:
                    LOG(str(e), 1)
                
                time.sleep(15)

#######

class TelexTwitterV2(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'TwtV2'
        self.params = params


        self._rx_buffer = []
        self._tx_buffer = []

        # init Twitter Client
        self._twitter_client = Twitter_Client_V2(
            params.get("consumer_key", ""), 
            params.get("consumer_secret", ""), 
            params.get("access_token", ""), 
            params.get("access_token_secret", ""), 
            params.get("bearer_token", ""),  
            params.get("user_mentions", "")
        )
        self._running = True
        LOG("Starting thread function")
        self._thread = threading.Thread(target=self.thread_function, name='Twitter_Handler_V2')
        self._thread.start()


    def __del__(self):
        super().__del__()
        self._running = False
        self._twitter_client.stop()
        self._thread.join()

    # =====

    def read(self) -> str:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            return

        if a == '\n':
            if self._tx_buffer:
                s = ''.join(self._tx_buffer)

                r = self._twitter_client.send_msg(s)
                self._tx_buffer = []

        elif a == '\r':
            pass
        else:
            self._tx_buffer.append(a)


    def thread_function(self):
        """
            Twitter client handler
        """
        while self._running:
            if not self._twitter_client.q.empty() :
                try:
                    linewidth = 68
                    data = self._twitter_client.q.get()
                    lines = str(data['escaped']).split("\n")
                    out_lines = []
                    for line in lines:
                        bmc = txCode.BaudotMurrayCode.ascii_to_tty_text(line.strip())
                        bmc = bmc.replace("@","(A)")
                        while len(bmc) >= linewidth:
                            out_lines.append(bmc[0:linewidth])
                            bmc = bmc[linewidth:]
                        out_lines.append(bmc)
                    tweet_txt_out = "\r\n\r".join(out_lines)

                    msg = "\r---\r\n\r{}\r\n\r{} (@{})\r\n\r{}\r\r\n---\r\n\r\n\r".format(
                          tweet_txt_out,
                          data['user']['name'],
                          data['user']['username'],
                          data['tweet']["created_at"]
                    )
                    msg = msg.replace("@", "(A)")

                    text = txCode.BaudotMurrayCode.ascii_to_tty_text(msg)
                    for c in text:
                        self._rx_buffer.append(c)

                except Exception as e:
                   LOG("txDevTwitterV2.thread_function: {}".format(str(e)),1)

        LOG('end twitter handler', 2)
