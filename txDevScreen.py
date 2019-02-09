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

from colorama import init, Fore, Back, Style   # https://pypi.org/project/colorama/
init()
import os

import txBase
import txCode

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


#######

class TelexScreen(txBase.TelexBase):
    _replace_char = {
        #'~': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',   # debug
        '*': 'THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG',
        '\r': '\r\n',
        '<': '\r',
        '|': '\n',
        '\x08': 'e e e ',
        }
    _replace_ctrl = {
        b'H': 'U',   # Cursor up
        b'P': 'D',   # Cursor down
        b'K': 'L',   # Cursor left
        b'M': 'R',   # Cursor right
        b'G': 'H',   # Home
        b'O': 'E',   # End
        b'R': 'I',   # Ins
        b'S': 'L',   # Del
        b'I': '\x1bA',   # Page up
        b'Q': '\x1bZ',   # Page down
        }

    def __init__(self, mode:str, **params):
        '''Creates a Screen object that you can call to do various keyboard things. '''

        super().__init__()

        self.id = '_'
        self.params = params

        self._rx_buffer = []
        self._escape = ''

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


    def set_normal_term(self):
        ''' Resets to normal terminal.  On Windows this is a no-op.
        '''
        
        if os.name == 'nt':
            pass
        
        else:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

    # =====

    def read(self) -> str:
        ret = ''
        
        if self.kbhit():
            k = self.getch()
            if k:
                if k == b'\xe0':
                    k = self.getch()
                    c = self._replace_ctrl.get(k, '')
                    if c:
                        self._rx_buffer.append(c)
                    return '' # eat cursor and control keys
                if k == b'\x1b':
                    self._escape = '\x1b'
                    return ''

                if os.name == 'nt':
                    c = k.decode('latin-1', errors='ignore')
                else:
                    c = k

                if self._escape:
                    if c == '\r':
                        self._escape = self._escape.upper()
                        self._rx_buffer.append(self._escape)
                        print('\033[1;37;41m<'+self._escape[1:]+'>\033[0m', end='', flush=True)
                        self._escape = ''
                    else:
                        self._escape += c
                else:
                    c = self._replace_char.get(c, c)
                    c = txCode.BaudotMurrayCode.translate(c)

                    for a in c:
                        self._rx_buffer.append(a)

                        # local echo
                        if a == '\r' or a == '\n':
                            print(a, end='')
                        else:
                            print('\033[31m'+a+'\033[0m', end='', flush=True)

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
            if a[0] == '\x1b':
                print('\033[0;30;47m<'+a[1:]+'>\033[0m', end='', flush=True)
            return

        if a == '\r' or a == '\n':
            print(a, end='')
        else:
            print(a, end='', flush=True)

    # =====

    def getch(self):
        ''' Returns a keyboard character after kbhit() has been called. '''

        if os.name == 'nt':
            return msvcrt.getch()
            #return msvcrt.getch().decode('iso_8859_1', errors='ignore')
            #return msvcrt.getch().decode('utf-8', errors='ignore')
            #return msvcrt.getch().decode('latin-1', errors='ignore')

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
