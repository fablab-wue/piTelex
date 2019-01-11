#!/usr/bin/python
"""
Load COnfiguration
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import time
#import threading
from argparse import ArgumentParser
import json

#######
# definitions and configuration


#######
# global variables

ARGS = None
CFG = {}

#######
# -----


# =====

def load():
    global ARGS, CFG

    with open('txConfig.json', 'r') as fp:
        CFG = json.load(fp)

    if not CFG['devices']:
        CFG['devices'] = {}

    parser = ArgumentParser(prog='-=TEST-TELEX=-', conflict_handler='resolve')

    parser.add_argument("-d", "--id", 
        dest="wru_id", default='', metavar="ID",
        help="Set the ID of the Telex Device. Leave empty to use the Hardware ID")

    parser.add_argument("-l", "--noloop",
        dest="loop", default=True, action="store_false", 
        help="No Loop-Back")
    parser.add_argument("-L", "--loop",
        dest="loop", default=True, action="store_true", 
        help="Use Loop-Back")

    parser.add_argument("-q", "--quiet",
        dest="verbose", default=True, action="store_false", 
        help="don't print status messages to stdout")


    parser.add_argument("-S", "--noscreen",
        dest="screen", default=True, action="store_false", 
        help="Device: No Screen in/out")

    parser.add_argument("-Y", "--tty", 
        dest="tty", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="Device: Use Virtual Serial Line (CH340) to communicate with Teletype")

    parser.add_argument("-G", "--gpio",
        dest="gpio", default=False, action="store_true", 
        help="Device: Use GPIO (pigpio) on RPi")

    parser.add_argument("-D", "--ed1000",
        dest="ed1000", default=False, action="store_true", 
        help="Device: Use ED1000 (Tx only) on Sound Card")

    parser.add_argument("-T", "--term", 
        dest="port", default=0, metavar='PORT', type=int,
        help="Device: Use Terminal Socket Server at Port Number")

    parser.add_argument("-E", "--eliza",
        dest="eliza", default=False, action="store_true", 
        help="Device: Use Eliza Chat Bot")

    ARGS = parser.parse_args()

    devices = CFG['devices']
    
    if 'screen' not in devices and ARGS.screen:
        devices['screen'] = {'type': 'screen'}

    if 'tty' not in devices and ARGS.tty:
        devices['tty'] = {'type': 'tty', 'portname': ARGS.tty.strip(), 'loopback': ARGS.loop}

    if 'gpio' not in devices and ARGS.gpio:
        devices['gpio'] = {'type': 'gpio', 'pin_txd': 17, 'pin_rxd': 27, 'pin_dtr': 22, 'pin_rts': 10, 'inv_txd': False, 'inv_rxd': False}

    if 'ed1000' not in devices and ARGS.ed1000:
        devices['ed1000'] = {'type': 'ed1000', 'f0': 500, 'f1': 700, 'baudrate': 50}

    if 'term' not in devices and ARGS.port:
        devices['term'] = {'type': 'term', 'port': ARGS.port}

    if 'eliza' not in devices and ARGS.eliza:
        devices['eliza'] = {'type': 'eliza'}


    CFG['verbose'] = ARGS.verbose
    CFG['wru_id'] = ARGS.wru_id

#######

