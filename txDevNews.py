#!/usr/bin/python3
"""
Telex Device - Scanning for news in files
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import time
# pip install watchdog
from watchdog.observers import Observer  
from watchdog.events import PatternMatchingEventHandler  

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase

#######

class TelexNews(txBase.TelexBase):
    class EventHandler(PatternMatchingEventHandler):
        patterns = ["*.txt", "*.rsstx", "*.news"]
        _last_path = ''
        _last_text = ''

        def __init__(self, buffer:list):
            super().__init__()
            self._news_buffer = buffer


        def on_modified(self, event):
            """
            event.event_type 
                'modified' | 'created' | 'moved' | 'deleted'
            event.is_directory
                True | False
            event.src_path
                path/to/observed/file
            """
            try:
                path = event.src_path
                with open(path) as fp:
                    text = fp.read()
                    text = text.replace('\n', '\r\n')
                    if path != self._last_path or text != self._last_text:
                        #print(repr(text))
                        self._last_path = path
                        self._last_text = text
                        if text:
                            # if self._print_path: # FIXME: this breaks due to attempting to access outer class (oversight), removed pending a suitable way to access config statically
                            #    path = path[:-4].replace('\\', '/')
                            #    text = path + '\r\n' + '='*len(path) + '\r\n' + text
                            self._news_buffer.append(text)
            except:
                pass

        def on_created(self, event):
            pass

    # =====

    def __init__(self, **params):
        super().__init__()

        self.id = '"'
        self.params = params

        self._newspath = params.get('newspath', './news')
        self._print_path = self.params.get('print_path', False)
        self._rx_buffer = []
        self._news_buffer = []
        self._state_counter = 1

        self._observer = Observer()
        self._observer.schedule(self.EventHandler(self._news_buffer), path=self._newspath, recursive=True)
        self._observer.start()


    def __del__(self):
        self.exit()
        super().__del__()
    

    def exit(self):
        self._observer.stop()
    
    # =====

    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a == '\x1bA':   # start session
                self._state_counter = 0
            if a == '\x1bZ':   # end session
                self._state_counter = 1
            if a == '\x1bWB':   # ready for dial
                self._state_counter = 0
            return


    def idle20Hz(self):
        if self._news_buffer and self._state_counter:
            self._state_counter += 1
            
            if self._state_counter == 2:
                self._rx_buffer.append('\x1bA')

            if self._state_counter > 25:
                text = self._news_buffer.pop(0)
                aa = txCode.BaudotMurrayCode.translate(text)
                aa = '\r\n' + aa + '\r\n\r\n\r\n'
                for a in aa:
                    self._rx_buffer.append(a)


#######

