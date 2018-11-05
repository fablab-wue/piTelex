#!/usr/bin/python
"""
Screen.py
Nonblocking read single character from screen/keyboard
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import os
import txBase

# Windows
if os.name == 'nt':
    import msvcrt

# Posix (Linux, OS X)
else:
    import sys
    import termios
    import atexit
    from select import select

#######

valid_char = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-+/=()$.,:!?\'%@#>'
replace_char = {
    '*': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',   # debug
    '&': '(AND)',
    '€': '($)',
    'Ä': 'AE',
    'Ö': 'OE',
    'Ü': 'UE',
    'ß': 'SS',
    '\r': '\r\n',
    '\t': '(TAB)',
    '~': '\a',
    '>': '\r',
    '|': '\n',
    '_': '...',
    ';': ',',
    '[': '((',
    ']': '))',
    '{': '(((',
    '}': ')))',
    '"': "'",
    '\x1B': '(ESC)',
    '\x08': '(BACK)',
    }

#######

class TelexScreen(txBase.TelexBase):

    def __init__(self):
        '''Creates a Screen object that you can call to do various keyboard things. '''

        super().__init__()

        self.id = '_'

        if os.name == 'nt':
            pass

        else:
            # Save the terminal settings
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)

            # Support normal-terminal reset at exit
            atexit.register(self.set_normal_term)


    def __del__(self):
        ''' Resets to normal terminal.  On Windows this is a no-op. '''
        #print('__del__ in Screen')

        if os.name == 'nt':
            pass

        else:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)
        super().__del__()

    # =====

    def read(self) -> str:
        if not self.kbhit():
            return ''
        c = self.getch() #'à'
        if c:
            c = c.upper()
            if c not in valid_char:
                c = replace_char.get(c, '?')
        return c


    def write(self, c:str, source:str):
        if c == '\r' or c == '\n':
            print(c, end='')
        else:
            print(c, end='', flush=True)

    # =====

    def getch(self):
        ''' Returns a keyboard character after kbhit() has been called. '''

        if os.name == 'nt':
            return msvcrt.getch().decode('latin-1', errors='ignore')
            #return msvcrt.getch().decode('iso_8859_1', errors='ignore')
            #return msvcrt.getch().decode('utf-8', errors='ignore')
            #return msvcrt.getch()

        else:
            return sys.stdin.read(1)


    def kbhit(self):
        ''' Returns True if keyboard character was hit, False otherwise. '''
        if os.name == 'nt':
            return msvcrt.kbhit()

        else:
            dr, dw, de = select([sys.stdin], [], [], 0)
            return dr != []

#######
