#!/usr/bin/python3

"""
Simple Telex RSS Client

requires feedparser
pip3 install feedparser

To turn this module on add the following to the devices section of the configuration

    "rss" : {
      "type" : "rss",
      "urls" : [
        "http://rss.cnn.com/rss/edition.rss"
      ],
      "format" : "{title}\n\r{description}\r\n{pubDate}\r\n{guid}\r\r---\r\n",
      "enable" : true
    }

"""
__author__ = "Frank BreBreedijk"
__license__ = "CC0"
__version__ = "0.5.0"


import threading
import time
import datetime
import queue

import json

import txBase
import txCode

import log
import logging
import feedparser
import re
import time


logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

def LOG(text:str, level:int=3):
    log.LOG('\033[5;30;46m<'+text+'>\033[0m', level)




#######
class RSS_Client():

   def __init__(self, urls):
        LOG("Starting rss client")
        self.q = queue.Queue()
        self._urls = urls
        self.running = True
        self.thread = threading.Thread(target=self.thread_function, name='RSS_Client')
        self.thread.start()

   def stop(self, quit_msg='Wah!'):
        self.running = False
        self.thread.join()

        del self


   def thread_function(self):
        feeds = {}
        for url in self._urls:
            feeds[url] = None
            LOG('Monitoring {}'.format(str(url)),3)
        print(feeds)
        while self.running:
            try:
                for url in self._urls:
                    rss = feedparser.parse(url)
                    if len(rss['items']) > 0 :
                        items = []
                        if feeds[url] :
                            for item in rss['items']:
                                if item['guid'] == feeds[url] :
                                    break
                                else :
                                    items.append(item)
                        else:
                            items = rss['items'][:3]
                        for item in items[::-1] :
                            self.q.put(item)
                        feeds[url] = rss['items'][0]['guid']
                time.sleep(60)
            except Exception as e:
                LOG("Error in rss client: {}".format(str(e)), 1)
            

#######

class TelexRSS(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'rss'
        self.params = params


        self._rx_buffer = []
        self._tx_buffer = []

        # init Client
        self._rss_client = RSS_Client(
            params.get("urls", [])
        )
        self._format=params.get("format","{title}\n")
        self._running = True
        self._thread = threading.Thread(target=self.thread_function, name='RSS_Handler')
        self._thread.start()


    def __del__(self):
        super().__del__()
        self._running = False
        self._rss_client.stop()
        self._thread.join()

    # =====

    def read(self) -> str:
        ret = ''

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        pass

    def thread_function(self):
        """
            RSS client handler
        """
        formatstr = self._format
        elements = []
        for match in re.findall("\{.*?\}",self._format):
            formatstr = formatstr.replace(match,"{}")
            matchstr=str(match)
            matchstr=matchstr.replace("{","")
            matchstr=matchstr.replace("}","")
            elements.append(matchstr)
        while self._running:
            if not self._rss_client.q.empty() :
                try:
                    data = self._rss_client.q.get()
                    values = []
                    for e in elements :
                        if e == "published" :
                            pubTime = data.get("published_parsed",None)
                            if pubTime :
                                values.append(time.strftime("%d-%m-%y %H:%M:%S",pubTime))
                            else:
                                values.append(None)
                        else :
                            values.append(data.get(e,""))
                    lines = []
                    out_lines = []
                    msg = formatstr.format(*values)
                    lines = str(msg).split("\n")
                    linewidth = 68

                    for line in lines:
                        bmc = txCode.BaudotMurrayCode.ascii_to_tty_text(line.strip())
                        bmc = bmc.replace("@","(at)")
                        while len(bmc) > linewidth:
                            # Das Blank kurz vor Zeilenende finden
                            lastblank = nextblank = 0
                            while (nextblank < linewidth) and (nextblank >= 0):
                                lastblank = nextblank
                                nextblank = bmc.find(" ",lastblank +1)
                            # Zeile bis zum gefundenen Blank ausgeben
                            out_lines.append(bmc[:lastblank].lstrip())

                            # Puffer entsprechend verkürzen
                            bmc = bmc[lastblank:].lstrip()
                        # rest ausgeben
                        out_lines.append(bmc)
                    
                    # Put the parts together
                    txt_out = "\r\n".join(out_lines)

                    # message is now fomatted, turn on printer
                    self._rx_buffer.append('\x1bA')
                    # insert formatted text into stream
                    for a in txt_out:
                        self._rx_buffer.append(a)


                except Exception as e:
                   LOG("txDevRSS.thread_function: {}".format(str(e)),1)

        # switch off printer
        self._rx_buffer.append('\x1bZ')

        LOG('end rss handler', 2)
