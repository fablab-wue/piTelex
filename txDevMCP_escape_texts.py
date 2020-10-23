#!/usr/bin/python3
"""
Telex Device - Master-Control-Module (MCP)
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.1.0"


escape_texts = {
    'RY':   # print RY pattern (64 characters = 10sec@50baud)
        'RY'*32,

    'FOX':   # print RY pattern (? characters = 10sec@50baud)
        'THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG',

    'PELZE':   # print RY pattern (? characters = 10sec@50baud)
        'KAUFEN SIE JEDE WOCHE VIER GUTE BEQUEME PELZE XY 1234567890',

    'ABC':   # print ABC pattern (51 characters = 7.6sec@50baud)
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890 .,-+=/()?\'%',

    'A1':   # print Bi-Zi-change pattern (? characters = 7.6sec@50baud)
        'A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z%',

    'LOREM':   # print LOREM IPSUM (460 characters = 69sec@50baud)
        '''\r
LOREM IPSUM DOLOR SIT AMET, CONSECTETUR ADIPISICI ELIT,\r
SED EIUSMOD TEMPOR INCIDUNT UT LABORE ET DOLORE MAGNA ALIQUA.\r
UT ENIM AD MINIM VENIAM, QUIS NOSTRUD EXERCITATION ULLAMCO\r
LABORIS NISI UT ALIQUID EX EA COMMODI CONSEQUAT. QUIS AUTE IURE\r
REPREHENDERIT IN VOLUPTATE VELIT ESSE CILLUM DOLORE EU FUGIAT\r
NULLA PARIATUR. EXCEPTEUR SINT OBCAECAT CUPIDITAT NON PROIDENT,\r
SUNT IN CULPA QUI OFFICIA DESERUNT MOLLIT ANIM ID EST LABORUM.\r
''',

    'LOGO':   # print piTelex logo (380 characters = 57sec@50baud)
        '''\r
-----------------------------------------------------\r
      OOO   OOO  OOOOO  OOOO  O     OOOO  O   O\r
      O  O   O     O    O     O     O      O O\r
      OOO    O     O    OOO   O     OOO     O\r
.....................................................\r
      O      O     O    O     O     O      O O\r
      O     OOO    O    OOOO  OOOO  OOOO  O   O\r
-----------------------------------------------------\r
''',

    'TEST':   # print test pattern (546 characters = 82sec@50baud)
        '''\r
.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.\r
-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-\r
=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=\r
X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X\r
=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=\r
-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-.-=X=-''',
}
