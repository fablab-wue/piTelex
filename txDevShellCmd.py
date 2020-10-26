#!/usr/bin/python3
"""
Telex Device - Execute a shell command on ESC sequences

"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import time

import logging
l = logging.getLogger("piTelex." + __name__)

import txCode
import txBase
import log

import os

import logging
l = logging.getLogger("piTelex." + __name__)

import txBase
import txCode

# Windows
if os.name == 'nt':
    #raise Exception('Works only on Linux')
    pass

# Posix (Linux, OS X)
else:
    import subprocess

#######

class TelexShellCmd(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'ShC'
        self.params = params

        self._LUT = {}
        lut = params.get('LUT', {})
        for keystr, cmd in lut.items():
            keys = keystr.split(',')
            for key in keys:
                self._LUT[key.upper().strip()] = cmd

        self._rx_buffer = []

    # -----

    def exit(self):
        pass

    # -----

    def __del__(self):
        super().__del__()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)
            return ret

    # -----

    def write(self, a:str, source:str):
        if len(a) > 1 and a[0] == '\x1b':
            a = a[1:].upper().strip()
            cmd = self._LUT.get(a, '')
            if cmd:
                l.info('execut for {} command {}'.format(a, cmd))
                #print('execut for {} command {}'.format(a, cmd))
                #subprocess.check_call(['iptables', '-t', 'nat', '-A',
                #       'PREROUTING', '-p', 'tcp',
                #       '--destination-port', '80',
                #       '-j', 'REDIRECT', '--to-port', '8080'])
                os.system(cmd)

    # =====

#######
