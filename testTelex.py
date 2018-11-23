#!/usr/bin/python
"""
testTelex for RPi Zero W or PC
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txController

import time
import threading
from argparse import ArgumentParser

#######
# definitions and configuration


#######
# global variables

ARGS = None
DEVICES = []

#######
# -----


# =====

def init():
    global ARGS, DEVICES

    ctrl = txController.TelexController(ARGS.id.strip())
    DEVICES.append(ctrl)

    if ARGS.screen:
        import txScreen
        screen = txScreen.TelexScreen()
        DEVICES.append(screen)

    if ARGS.tty:
        import txSerial
        serial = txSerial.TelexSerial(ARGS.tty.strip(), ARGS.loop)
        DEVICES.append(serial)

    if ARGS.pin:
        import txPiGPIO
        serial = txPiGPIO.TelexPiGPIO(17, 27, 22, 10)
        DEVICES.append(serial)

    if ARGS.port:
        import txWebSrv
        srv = txWebSrv.TelexWebSrv(ARGS.port)
        DEVICES.append(srv)

    if ARGS.eliza:
        import txEliza
        eliza = txEliza.TelexEliza()
        DEVICES.append(eliza)

# =====

def exit():
    global ARGS

    pass

# =====

def loop():
    global ARGS

    for in_device in DEVICES:
        c = in_device.read()
        if c:
            for out_device in DEVICES:
                if out_device != in_device:
                    if out_device.write(c, in_device.id):
                        break
    
    for device in DEVICES:
        device.idle()

    return

# =====

def main():
    global ARGS

    parser = ArgumentParser(prog='-=TEST-TELEX=-', conflict_handler='resolve')

    parser.add_argument("-t", "--tty", 
        dest="tty", default='', metavar="TTY",   # '/dev/serial0'   '/dev/ttyUSB0'
        help="Set serial port name communicating with Teletype")

    parser.add_argument("-d", "--id", 
        dest="id", default='', metavar="ID",
        help="Set the ID of the Telex Device. Leave empty to use the Hardware ID")

    parser.add_argument("-E", "--eliza",
        dest="eliza", default=False, action="store_true", 
        help="Use Eliza Chat Bot")

    parser.add_argument("-l", "--noloop",
        dest="loop", default=True, action="store_false", 
        help="No Loop-Back")
    parser.add_argument("-L", "--loop",
        dest="loop", default=True, action="store_true", 
        help="Use Loop-Back")

    parser.add_argument("-s", "--noscreen",
        dest="screen", default=True, action="store_false", 
        help="No Screen in/out")

    parser.add_argument("-p", "--pin", 
        dest="pin", default=0, metavar='GPIO', type=int,
        help="GPIO Number")

    parser.add_argument("-P", "--port", 
        dest="port", default=0, metavar='PORT', type=int,
        help="Port Number for Socket Server")

    parser.add_argument("-q", "--quiet",
        dest="verbose", default=True, action="store_false", 
        help="don't print status messages to stdout")

    ARGS = parser.parse_args()

    init()

    print('-=TELEX=-')

    try:
        while True:
            loop()
            time.sleep(0.001)   # update with max ??? Hz

    except (KeyboardInterrupt, SystemExit):
        pass

    except:
        raise

    finally:
        exit()

#######

if __name__== "__main__":
    main()

