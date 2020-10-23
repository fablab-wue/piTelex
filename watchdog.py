#!/usr/bin/python3
"""
Telex Device - Master-Control-Module (MCP)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.1.0"

import time
import os

import logging
l = logging.getLogger("piTelex." + __name__)

#######

class Watchdog():
    def __init__(self):
        self._wds = {}

    def init(self, name:str, callback, time_out_period:int, abort_period:int=None):
        wd = {}
        wd['callback'] = callback
        wd['time_out_period'] = time_out_period
        wd['abort_period'] = abort_period
        wd['time_out'] = None
        wd['time_abort'] = None
        self._wds[name] = wd

    def restart(self, name:str, temp_time_out_period:int=0):
        wd = self._wds[name]
        top = wd['time_out_period']
        if temp_time_out_period:
            top = temp_time_out_period
        if top:
            wd['time_out'] = time.time() + top
        if not wd['time_abort'] and wd['abort_period']:
            wd['time_abort'] = time.time() + wd['abort_period']

    def restart_if_active(self, name:str):
        if self._wds[name]['time_out']:
            self.restart(name)

    def disable(self, name:str):
        self._wds[name]['time_out'] = None
        self._wds[name]['time_abort'] = None

    def is_active(self, name:str):
        return self._wds[name]['time_out']

    def process(self):
        time_act = time.time()

        for name, wd in self._wds.items():
            if wd['time_out']:
                if  time_act > wd['time_out']:
                    wd['time_out'] = None
                    wd['time_abort'] = None
                    wd['callback'](name)
                    l.debug("Watchdog {!r}: {!r}".format(name, wd["callback"]))
            if wd['time_abort']:
                if  time_act > wd['time_abort']:
                    wd['time_out'] = None
                    wd['time_abort'] = None
                    wd['callback'](name+'_ABORT')
                    l.debug("Watchdog {!r}_ABORT: {!r}".format(name, wd["callback"]))

#######