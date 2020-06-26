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
from argparse import ArgumentParser
import json

import log
import logging
l = logging.getLogger("piTelex." + __name__)

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

    parser = ArgumentParser(
        prog='telex', 
        conflict_handler='resolve', 
        description='Handle historic teletypes.', 
        epilog='More infos at https://github.com/fablab-wue/piTelex.git',
        allow_abbrev=True)

    gi = parser.add_argument_group("Interfaces")

    gi.add_argument("-G", "--RPiTW39",
        dest="RPiTTY", default=False, action="store_true", 
        help="GPIO (pigpio) on RPi with TW39 teletype")

    gi.add_argument("-Y", "--tty", 
        dest="CH340", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-Serial-Adapter (CH340-chip) with teletype (without dialing)")

    gi.add_argument("-W", "--ttyTW39", 
        dest="CH340_TW39", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-Serial-Adapter (CH340-chip) with TW39 teletype (pulse dial)")

    gi.add_argument("-M", "--ttyTWM", 
        dest="CH340_TWM", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-Serial-Adapter (CH340-chip) with TWM teletype (keypad dial)")

    gi.add_argument("-V", "--ttyV10", 
        dest="CH340_V10", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-Serial-Adapter (CH340-chip) with V.10 teletype (FS200, FS220)")

    gi.add_argument("-E", "--audioED1000",
        dest="ED1000", default=False, action="store_true", 
        help="USB-Sound-Card with ED1000 teletype")

    gi.add_argument("--noscreen",
        dest="screen", default=True, action="store_false", 
        help="No Screen in/out")


    gg = parser.add_argument_group("Gateways")

    gg.add_argument("-I", "--iTelex", 
        dest="itelex", default=-1, const=0, nargs='?', metavar='PORT', type=int,
        help="i-Telex Client and Server (if PORT>0)")

    #gg.add_argument("-T", "--telnet", 
    #    dest="telnet", default=0, metavar='PORT', type=int,
    #    help="Terminal Socket Server at Port Number")

    gg.add_argument("-N", "--news", 
        dest="news", default='', metavar="PATH",
        help="News from File")

    gg.add_argument("-C", "--IRC", 
        dest="irc", default='', metavar="CHANNEL",
        help="IRC Client")

    gg.add_argument("-R", "--REST", 
        dest="rest", default='', metavar="TEMPLATE",
        help="REST Client")

    gg.add_argument("-Z", "--eliza",
        dest="eliza", default=False, action="store_true", 
        help="Eliza chat bot")


    gd = parser.add_argument_group("Debug")

    gd.add_argument("-L", "--log", 
        dest="log", default='', metavar="FILE",
        help="Log to File")

    gd.add_argument("-d", "--debug", 
        dest="debug", default=0, metavar='LEVEL', type=int,
        help="Debug level")


    parser.add_argument("-c", "--config", 
        dest="cnf", default='txConfig.json', metavar="FILE",
        help="Load Config File (JSON)")

    parser.add_argument("-k", "--id", "--KG", 
        dest="wru_id", default='', metavar="ID",
        help="Set the ID of the Telex Device. Leave empty to use the Hardware ID")

    #parser.add_argument("-m", "--mode", 
    #    dest="mode", default='', metavar="MODE",
    #    help="Set the mode of the Telex Device. e.g. TW39, TWM, V.10")

    parser.add_argument("-q", "--quiet",
        dest="verbose", default=True, action="store_false", 
        help="don't print status messages to stdout")

    parser.add_argument("-s", "--save",
        dest="save", default=False, action="store_true", 
        help="Save command line args to config file (txConfig.json)")


    ARGS = parser.parse_args()

    try:
        with open(ARGS.cnf, 'r') as fp:
            CFG = json.load(fp)
    except:
        CFG = {}

    if not CFG.get('devices', None):
        CFG['devices'] = {}

    devices = CFG['devices']
    
    if ARGS.screen:
        screen_args = {'type': 'screen', 'enable': True, 'lowercase': False, 'suppress_shifts': False}
        try:
            screen_args.update(devices['screen'])
        except KeyError:
            devices['screen'] = screen_args

    if ARGS.CH340:
        devices['CH340'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340.strip(), 'mode': '', 'baudrate': 50, 'loopback': True}

    if ARGS.CH340_TW39:
        devices['CH340_TW39'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340_TW39.strip(), 'mode': 'TW39', 'baudrate': 50, 'loopback': True}

    if ARGS.CH340_TWM:
        devices['CH340_TWM'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340_TWM.strip(), 'mode': 'TWM', 'baudrate': 50, 'loopback': True}

    if ARGS.CH340_V10:
        devices['CH340_V10'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340_V10.strip(), 'mode': 'V10', 'baudrate': 50, 'loopback': False}

    if ARGS.RPiTTY:
        devices['RPiTTY'] = {
            'type': 'RPiTTY',
            'enable': True, 
            'pin_txd': 17, 
            'pin_rxd': 27, 
            'pin_fsg_ns': 6,
            'pin_rel': 22, 
            'pin_oin': 10, 
            'pin_opt': 9, 
            'pin_dir': 11, 
            'pin_sta': 23,
            'baudrate': 50, 
            'inv_rxd': False, 
            'coding': 0,
            'loopback': True,
            }

    if ARGS.ED1000:
        devices['ED1000'] = {
            'type': 'ED1000',
            'enable': True, 
            'send_f0': 500, 
            'send_f1': 700, 
            'recv_f0': 2250, 
            'recv_f1': 3150,
            'recv_squelch': 100,
            'recv_debug': False,
            'baudrate': 50, 
            'devindex': None, 
            'zcarrier': False,
            }

    #if ARGS.telnet:
    #    devices['telnet'] = {'type': 'telnet', 'enable': True, 'port': ARGS.telnet}

    if ARGS.itelex >= 0:
        devices['i-Telex'] = {'type': 'i-Telex', 'enable': True, 'port': ARGS.itelex, 'number': 0, 'tns-pin': 12345}

    if ARGS.news:
        devices['news'] = {'type': 'news', 'enable': True, 'newspath': ARGS.news.strip()}

    if ARGS.irc:
        devices['IRC'] = {'type': 'IRC', 'enable': True, 'channel': ARGS.irc.strip()}

    if ARGS.rest:
        devices['REST'] = {'type': 'REST', 'enable': True, 'template': ARGS.rest.strip()}

    if ARGS.eliza:
        devices['eliza'] = {'type': 'eliza', 'enable': True}

    if ARGS.log:
        devices['log'] = {'type': 'log', 'enable': True, 'filename': ARGS.log.strip()}


    CFG['verbose'] = ARGS.verbose
    
    wru_id = ARGS.wru_id.strip().upper()
    if wru_id:
        CFG['wru_id'] = wru_id
    
    #mode = ARGS.mode.strip()
    #if mode:
    #    CFG['mode'] = mode

    if ARGS.debug:
        CFG['debug'] = ARGS.debug
    log.set_log_level(CFG.get('debug', 0))


    if ARGS.save:
        with open(ARGS.cnf, 'w') as fp:
            json.dump(CFG, fp, indent=2)

#######

