#!/usr/bin/python3
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

    parser.add_argument("-k", "--id", 
        dest="wru_id", default='', metavar="ID",
        help="Set the ID of the Telex Device. Leave empty to use the Hardware ID")

    parser.add_argument("-m", "--mode", 
        dest="mode", default='', metavar="MODE",
        help="Set the mode of the Telex Device. e.g. TW39, TWM, V.10")

    parser.add_argument("-q", "--quiet",
        dest="verbose", default=True, action="store_false", 
        help="don't print status messages to stdout")

    parser.add_argument("-s", "--save",
        dest="save", default=False, action="store_true", 
        help="Save command line args to config file")


    parser.add_argument("-S", "--noscreen",
        dest="screen", default=True, action="store_false", 
        help="Device: No Screen in/out")

    parser.add_argument("-Y", "--CH340TTY", 
        dest="CH340TTY", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="Device: Use Virtual Serial Line (CH340) to communicate with Teletype")

    parser.add_argument("-G", "--RPiTTY",
        dest="RPiTTY", default=False, action="store_true", 
        help="Device: Use GPIO (pigpio) on RPi")

    parser.add_argument("-E", "--ED1000",
        dest="ED1000", default=False, action="store_true", 
        help="Device: Use ED1000 (Tx only) on Sound Card")

    parser.add_argument("-T", "--telnet", 
        dest="telnet", default=0, metavar='PORT', type=int,
        help="Device: Use Terminal Socket Server at Port Number")

    parser.add_argument("-I", "--itelex", 
        dest="itelex", default=-1, metavar='PORT', type=int,
        help="Device: i-Telex Client and Server if PORT>0")

    parser.add_argument("-Z", "--eliza",
        dest="eliza", default=False, action="store_true", 
        help="Device: Use Eliza Chat Bot")

    parser.add_argument("-L", "--log", 
        dest="log", default='', metavar="NAME",
        help="Device: Log to File")

    ARGS = parser.parse_args()

    devices = CFG['devices']
    
    if ARGS.screen:
        devices['screen'] = {'type': 'screen'}

    if ARGS.CH340TTY:
        devices['CH340TTY'] = {'type': 'CH340TTY', 'portname': ARGS.CH340TTY.strip(), 'baudrate': 50, 'loopback': True}

    if ARGS.RPiTTY:
        devices['RPiTTY'] = {'type': 'RPiTTY', 'pin_txd': 17, 'pin_rxd': 27, 'pin_rel': 22, 'pin_oin': 10, 'pin_opt': 9, 'pin_dir': 11, 'baudrate': 50, 'inv_txd': False, 'inv_rxd': False, 'loopback': True}

    if ARGS.ED1000:
        devices['ED1000'] = {'type': 'ED1000', 'f0': 500, 'f1': 700, 'baudrate': 50}

    if ARGS.telnet:
        devices['telnet'] = {'type': 'telnet', 'port': ARGS.telnet}

    if ARGS.itelex >= 0:
        devices['i-Telex'] = {'type': 'i-Telex', 'port': ARGS.itelex}

    if ARGS.eliza:
        devices['eliza'] = {'type': 'eliza'}

    if ARGS.log:
        devices['log'] = {'type': 'log', 'filename': ARGS.log.strip()}


    CFG['verbose'] = ARGS.verbose
    
    wru_id = ARGS.wru_id.strip()
    if wru_id:
        CFG['wru_id'] = wru_id
    
    mode = ARGS.mode.strip()
    if mode:
        CFG['mode'] = mode


    if ARGS.save:
        with open('txConfig.json', 'w') as fp:
            json.dump(CFG, fp, indent=2)

#######

