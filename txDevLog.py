#!/usr/bin/python3
"""
Telex Device - Writing a log-file
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import time

import logging

from txReleaseInfo import ReleaseInfo
l = logging.getLogger("piTelex." + __name__)

import txBase

#######

class TelexLog(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'Log'
        self.params = params

        self._filename = params.get('filename', 'log.txt')

        self._last_time = self._last_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self._last_source = '   '
        self._line = '===== piTelex Rev. ' + ReleaseInfo.get_release_info()
        """
        try:
            from telex import find_rev
            rev = find_rev()
        except:
            pass
        else:
            self._line += 'rev ' + rev
        """
        # cut line to head, commit hash and max. 50 characters description
        # (as widely recommended)
        self._line = self._line[:77]
        self._line += ' '

        self._line += (80 - len(self._line)) * '='

    def __del__(self):
        self.exit()
        super().__del__()


    def exit(self):
        pass

    # =====

    def read(self) -> str:
        return ''


    def write(self, a:str, source:str):
        out = False
        add = ''

        if a == '\r':
            a = '\\'
        if a == '\n':
            a = '_'
        if a == '\t':
            a = '\\t'
        if len(a) > 1:
            # Print all commands, except WELCOME (internal use)
            if a[1:] == "WELCOME":
                return
            a = '{' + a[1:] + '}'

        if source == self._last_source and a == '_':
            out = True
            add = '_'
            a = ''

        elif source == self._last_source and len(self._line) >= 80:
            out = True
            add = '   |'

        if source != self._last_source:
            out = True

        if out:
            line = self._last_time
            line += ' ,'
            line += self._last_source
            line += ', '
            line += self._line
            line += add

            with open(self._filename, 'a', encoding='UTF-8') as fp:
                line += '\n'
                fp.write(line)

            self._line = ''
            self._last_time = ''
            self._last_source = source

        self._line += a

        if not self._last_time:
            self._last_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


#######

