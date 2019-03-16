#!/usr/bin/python3
"""
Telex Device - Keyboard input and Screen output
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
    import tty
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
        b'H': '\x1bCU',   # Cursor up
        b'P': '\x1bCD',   # Cursor down
        b'K': '\x1bCL',   # Cursor left
        b'M': '\x1bCR',   # Cursor right
        b'G': '\x1bLT',   # Home
        b'O': '\x1bST',   # End
        b'R': '\x1bAT',   # Ins
        b'S': '\x1bST',   # Del
        b'I': '\x1bA',    # Page up
        b'Q': '\x1bZ',    # Page down
        }
    _replace_escape = {
        '\x1b[a': '\x1bCU',    # Cursor up
        '\x1b[b': '\x1bCD',    # Cursor down
        '\x1b[d': '\x1bCL',    # Cursor left
        '\x1b[c': '\x1bCR',    # Cursor right
        '\x1b[1~': '\x1bLT',   # Home
        '\x1b[4~': '\x1bST',   # End
        '\x1b[2~': '\x1bAT',   # Ins
        '\x1b[3~': '\x1bST',   # Del
        '\x1b[5~': '\x1bA',    # Page up
        '\x1b[6~': '\x1bZ',    # Page down
        }

    def __init__(self, **params):
        '''Creates a Screen object that you can call to do various keyboard things. '''
        super().__init__()

        self.id = '_'
        self.params = params

        self._rx_buffer = []
        self._escape = ''

        if os.name == 'nt':
            pass

        else:   # Linux and RPi
            # Save the terminal settings
            #self.fd = os.fdopen(sys.stdin.detach().fileno(), 'rb', buffering=0)   # experimental
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)
            #tty.setraw(self.fd)
            #tty.cbreak(self.fd)

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
                #print(int(k))
                if k == b'\xe0':
                    k = self.getch()
                    c = self._replace_ctrl.get(k, '')
                    if c:
                        print('\033[0;37;41m<'+c[1:]+'>\033[0m', end='', flush=True)
                        self._rx_buffer.append(c)
                    return '' # eat cursor and control keys
                if k == b'\x1b' or k == '\x1b':
                    self._escape = '\x1b'
                    print('§', end='', flush=True)
                    return ''

                if os.name == 'nt':
                    c = k.decode('latin-1', errors='ignore')
                else:
                    c = k

                if self._escape:
                    if c == '\r' or c == '\n':
                        self._escape = self._escape.upper()
                        self._rx_buffer.append(self._escape)
                        print('\033[1;37;41m<'+self._escape[1:]+'>\033[0m', end='', flush=True)
                        self._escape = ''
                    else:
                        self._escape += c
                        c = self._replace_escape.get(self._escape, '')
                        if c:
                            self._escape = c
                            self._rx_buffer.append(self._escape)
                            print('\033[1;36;41m<'+self._escape[1:]+'>\033[0m', end='', flush=True)
                            self._escape = ''
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
            
            #dr, dw, de = select([self.fd], [], [], 0)

            return dr != []

#######
