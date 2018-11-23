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
        '\r': '\r\n',
        '<': '\r',
        '|': '\n',
        '\x1B': '(ESC)',
        '\x08': '(BACK)',
        }

    def __init__(self):
        '''Creates a Screen object that you can call to do various keyboard things. '''

        super().__init__()

        self.id = '_'

        self._rx_buffer = []

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
        ret = ''
        
        if self.kbhit():
            k = self.getch()
            if k:
                if k == b'\xe0':
                    k = self.getch()
                    return '' # eat cursor and control keys
                if k == b'\x1b':
                    return '' # eat escape

                c = k.decode('latin-1', errors='ignore')
                c = self._replace_char.get(c, c)
                c = txCode.BaudotMurrayCode.translate(c)

                for a in c:
                    self._rx_buffer.append(a)

        if self._rx_buffer:
            ret = self._rx_buffer.pop(0)

        return ret


    def write(self, a:str, source:str):
        if len(a) != 1:
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
