#!/usr/bin/python3
"""
Load COnfiguration
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.0.2"

import time
from argparse import ArgumentParser
try:
    import commentjson as json
    _commentjson_error = False
except:
    import json
    _commentjson_error = True

import log
import logging
l = logging.getLogger("piTelex." + __name__)

if _commentjson_error:
    # Presently, this will only log to console and not to the error log since
    # the latter is set up after configuration has been read successfully.
    l.warning("commentjson could not be imported; loading configuration from telex.json may fail if there are comments inside.")

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

    gi.add_argument("-C", "--RPiCtrl",
        dest="RPiCtrl", default=False, action="store_true",
        help="GPIO (pigpio) on RPi with button controls and LEDs")

    gi.add_argument("-X", "--terminal",
        dest="terminal", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="Serial terminal in 8-bit ASCII")

    gi.add_argument("-Y", "--tty",
        dest="CH340", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-serial-adapter (CH340-chip) with teletype (without dialing)")

    gi.add_argument("-W", "--ttyTW39",
        dest="CH340_TW39", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-serial-adapter (CH340-chip) with TW39 teletype (pulse dial)")

    gi.add_argument("-M", "--ttyTWM",
        dest="CH340_TWM", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-serial-adapter (CH340-chip) with TWM teletype (keypad dial)")

    gi.add_argument("-V", "--ttyV10",
        dest="CH340_V10", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="USB-serial-adapter (CH340-chip) with V.10 teletype (FS200, FS220)")

    gi.add_argument("-E", "--audioED1000",
        dest="ED1000", default=False, action="store_true",
        help="USB-sound-card with ED1000 teletype")

    gi.add_argument("--noscreen",
        dest="screen", default=True, action="store_false",
        help="No screen in/out")


    gg = parser.add_argument_group("Gateways")

    gg.add_argument("-I", "--iTelex",
        dest="itelex", default=-1, const=0, nargs='?', metavar='PORT', type=int,
        help="i-Telex client and server (if PORT>0)")

    gg.add_argument("-N", "--news",
        dest="news", default='', metavar="PATH",
        help="News from file")

    gg.add_argument("-T", "--twitter",
        dest="twitter", default='', nargs='?', metavar='CONSUMER_KEY:CONSUMER_SECRET:API_KEY:API_SECRET',
        help="Twitter client")


    gg.add_argument("-W", "--twitterv2",
        dest="twitter", default='', nargs='?', metavar='CONSUMER_KEY:CONSUMER_SECRET:ACCESS_TOKEN:ACCESS_TOKEN_SECRET:BEARER_TOKEN:USERNAME',
        help="V2 Twitter client")

    gg.add_argument("-S", "--rss",
        dest="rss", default='', nargs='?', metavar='url',
        help="RSS feed client (experimental)")

    gg.add_argument("-C", "--IRC",
        dest="irc", default='', metavar="CHANNEL",
        help="IRC client")

    gg.add_argument("-R", "--REST",
        dest="rest", default='', metavar="TEMPLATE",
        help="REST client")


    gt = parser.add_argument_group("Tools / Toys")

    gt.add_argument("-Z", "--eliza",
        dest="eliza", default=False, action="store_true",
        help="Eliza chat bot")

    gt.add_argument("-A", "--archive",
        dest="archive", default=False, action="store_true",
        help="Archive module")

    gt.add_argument("-S", "--shellcmd",
        dest="shellcmd", default=False, action="store_true",
        help="Execute shell command of ESC sequ.")

    gt.add_argument("-K", "--keypad",
        dest="keypad", default=False, action="store_true",
        help="KeyPad shortcuts")


    gd = parser.add_argument_group("Debug")

    gd.add_argument("-L", "--log",
        dest="log", default='', metavar="FILE",
        help="Log to file")

    gd.add_argument("-d", "--debug",
        dest="debug", default=0, metavar='LEVEL', type=int,
        help="Debug level")


    parser.add_argument("-c", "--config",
        dest="cnf_file", default='telex.json', metavar="FILE",
        help="Load config file (telex.json)")

    parser.add_argument("-k", "--id", "--KG",
        dest="wru_id", default='', metavar="ID",
        help="Enable software answerback unit and set the telex device ID. If "
                        "enabled and a WRU is received, the software answerback "
                        "will be triggered after 2 s if no hardware answerback "
                        "unit replies (fallback mode). Leave empty to use "
                        "hardware answerback unit only")

    parser.add_argument("--id-replace-always",
        dest="wru_replace_always", default=False, action="store_true",
        help="Enable if your teleprinter has no answerback unit: On receipt of "
                        "WRU, the configured software ID will be sent "
                        "immediately")

    parser.add_argument("--invert_dtr",
        dest="invert_dtr", default=False, action="store_true",
        help="Invert DTR")

    parser.add_argument("-t", "--track", nargs='*',
        dest="track", metavar="USERS", help="User list")

    parser.add_argument("-f", "--follow", nargs='*',
        dest="follow", metavar="USER", help="User list")

    parser.add_argument("-u", "--url", nargs='?',
        dest="url", metavar="URL", help="URL for twitivity")

    parser.add_argument("-h", "--host", nargs='?',
        dest="host", metavar="HOST", help="Host for twitivity")

    parser.add_argument("-p", "--port", nargs='?',
        dest="port", metavar="PORT", help="Port for twitivity")

    parser.add_argument("-l", "--languages", nargs='*',
        dest="languages", metavar="LANGUAGE", help="Language list")

    parser.add_argument("--errorlog-path",
        dest="errorlog_path", default="", metavar="ERRLOGPATH",
        help="Path of error log; relative paths are referred to where this program is being executed")

    parser.add_argument("--errorlog-level",
        dest="errorlog_level", default="", metavar="ERRLOGLEVEL",
        help="Verbosity of error log; see python log levels")

    parser.add_argument("-s", "--save",
        dest="save", default=False, action="store_true",
        help="Save command line args to config file (telex.json)")

    ARGS = parser.parse_args()

    try:
        with open(ARGS.cnf_file.strip(), 'r') as fp:
            CFG = json.load(fp)
    except FileNotFoundError:
        l.warning("Configuration file '{}' not found. Using CLI params only.".format(ARGS.cnf_file.strip()))
        CFG = {}
    except json.JSONDecodeError as e:
        l.warning("Configuration file '{}' error '{}' in line {} column {}".format(ARGS.cnf_file.strip(), e.msg, e.lineno, e.colno))
        exit()
    except Exception as e:
        l.warning("Configuration file '{}' damaged: ".format(ARGS.cnf_file.strip()))
        raise

    if not CFG.get('devices', None):
        CFG['devices'] = {}

    devices = CFG['devices']

    if ARGS.screen and 'screen' not in devices:
        devices['screen'] = {
            'type': 'screen',
            'enable': True,
            'show_BuZi': True,
            'show_capital': False,
            'show_ctrl': True,
            'show_info': False
            }

    if ARGS.terminal:
        devices['terminal'] = {
            'type': 'terminal',
            'enable': True,
            'portname': ARGS.terminal.strip(),
            'baudrate': 300,
            'bytesize': 8,
            'stopbits': 1,
            'parity': 'N',
            'loc_echo': True,
        }

    if ARGS.CH340:
        devices['CH340'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340.strip(), 'mode': '', 'baudrate': 50, 'loopback': True}

    if ARGS.CH340_TW39:
        devices['CH340_TW39'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340_TW39.strip(), 'mode': 'TW39', 'baudrate': 50, 'loopback': True, 'inverse_dtr': ARGS.invert_dtr}

    if ARGS.CH340_TWM:
        devices['CH340_TWM'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340_TWM.strip(), 'mode': 'TWM', 'baudrate': 50, 'loopback': True, 'inverse_dtr': ARGS.invert_dtr}

    if ARGS.CH340_V10:
        devices['CH340_V10'] = {'type': 'CH340TTY', 'enable': True, 'portname': ARGS.CH340_V10.strip(), 'mode': 'V10', 'baudrate': 50, 'loopback': False, 'inverse_dtr': ARGS.invert_dtr}

    if ARGS.RPiTTY:
        devices['RPiTTY'] = {
            'type': 'RPiTTY',
            'enable': True,
            'pin_txd': 17,
            'pin_rxd': 27,
            'inv_rxd': False,
            'pin_relay': 22,
            'inv_relay': False,
            'pin_dir': 0,
            'pin_number_switch': 6,
            'baudrate': 50,
            'coding': 0,
            'loopback': True,
            }

    if ARGS.RPiCtrl:
        devices['RPiCtrl'] = {
            'type': 'RPiCtrl',
            'enable': True,
            'pin_number_switch': 0,
            'inv_number_switch': 0,
            'pin_button_1T': 0,
            'pin_button_AT': 0,
            'pin_button_ST': 0,
            'pin_button_LT': 0,
            'pin_button_PT': 0,
            'pin_button_U1': 0,
            'pin_button_U2': 0,
            'pin_button_U3': 0,
            'pin_button_U4': 0,
            'pin_LED_A': 0,
            'pin_LED_WB': 0,
            'pin_LED_WB_A': 9,
            'pin_LED_status_R': 23,
            'pin_LED_status_G': 24,
            'pin_LED_LT': 0,
            'pin_power': 0,
            'inv_power': 0,
            'delay_AT': 0,
            'delay_ST': 0,
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
            'baudrate': 50,
            'devindex': None,
            'zcarrier': False,
            'unres_threshold': 100,
            }

    if ARGS.itelex >= 0:
        devices['i-Telex'] = {'type': 'i-Telex', 'enable': True, 'port': ARGS.itelex, 'tns_dynip_number': 0, 'tns_pin': 12345}

    if ARGS.news:
        devices['news'] = {'type': 'news', 'enable': True, 'newspath': ARGS.news.strip()}

    if ARGS.twitter:
        import os
        twit_creds = ARGS.twitter.split(":")
        os.environ['consumer_key'] = ARGS.consumer_key
        os.environ['consumer_secret'] = ARGS.consumer_secret
        devices['twitter'] = { 'type': 'twitter', 'enable'  : True, 'consumer_key' : twit_creds [0], 'consumer_secret' : twit_creds [1], 'access_token_key' : twit_creds [2], 'access_token_secret' : twit_creds [3] , 'track' : ARGS.track, 'follow': ARGS.follow, 'languages' : ARGS.languages, 'url' : ARGS.url, 'host' : ARGS.host, 'port' : ARGS.port }

    if ARGS.twitter:
        twit_args = ARGS.twitter.split(":")
        devices['twitterV2'] = { 'type': 'twitterv2', 'enable'  : True, 'consumer_key' : twit_args[0], 'consumer_secret' : twit_args[1], 'access_token' : twit_args[2], 'access_token_secret' : twit_args[3] , 'bearer_token' : twit_args[4], 'user_mentions':twit_args[5] }
    
    if ARGS.rss:
        devices['rss'] = {'type': "rss", 'urls' : [ ARGS.rss ], 'format': "{title}\n\r{description}\r\n{pubDate}\r\n{guid}\r\r---\r\n}"}

    if ARGS.irc:
        devices['IRC'] = {'type': 'IRC', 'enable': True, 'channel': ARGS.irc.strip()}

    if ARGS.rest:
        devices['REST'] = {'type': 'REST', 'enable': True, 'template': ARGS.rest.strip()}

    if ARGS.eliza:
        devices['eliza'] = {'type': 'eliza', 'enable': True}

    if ARGS.archive:
        devices['archive'] = {'type': 'archive', 'enable': True, 'path': 'archive'}

    if ARGS.shellcmd:
        devices['shellcmd'] = {'type': 'shellcmd', 'enable': True, 'LUT': { 'X': 'xxx'} }

    if ARGS.keypad:
        devices['KeyPad1'] = {
            'type': 'KeyPad', 
            'enable': True, 
            'device_name': 'KEYPAD', 
            'KEYS': { 
                'KEY_KP1': 'RY'*30, 
                'KEY_KPENTER': '\\_', 
                'KEY_KPPLUS': '{A}', 
                'KEY_KPMINUS': '{Z}',
                }
            }

    if ARGS.log:
        devices['log'] = {'type': 'log', 'enable': True, 'filename': ARGS.log.strip()}


    wru_id = ARGS.wru_id.strip().upper()
    if wru_id:
        CFG['wru_id'] = wru_id

    wru_replace_always = ARGS.wru_replace_always
    if wru_replace_always:
        CFG['wru_replace_always'] = wru_replace_always

    errorlog_path = ARGS.errorlog_path.strip()
    if errorlog_path:
        CFG['errorlog_path'] = errorlog_path

    errorlog_level = ARGS.errorlog_level.strip().upper()
    if errorlog_level:
        CFG['errorlog_level'] = errorlog_level


    if ARGS.debug:
        CFG['debug'] = ARGS.debug
    log.set_log_level(CFG.get('debug', 0))


    if ARGS.save:
        with open(ARGS.cnf_file, 'w') as fp:
            json.dump(CFG, fp, indent=2)

#######

