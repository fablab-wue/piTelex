#!/usr/bin/python
"""
testTelex for RPi Zero W
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txController
import txSerial
import txScreen

import time
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

    screen = txScreen.TelexScreen()
    DEVICES.append(screen)

    serial = txSerial.TelexSerial(ARGS.tty.strip())
    DEVICES.append(serial)

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
                        dest="tty", default='COM4', metavar="TTY",   # '/dev/ttyS0'   '/dev/ttyAMA0'
                        help="Set serial port name communicating with Telex")

    parser.add_argument("-d", "--id", 
                        dest="id", default='<test>', metavar="ID",
                        help="Set the ID of the Telex Device. Leave empty to use the Hardware ID")

    '''
    parser.add_argument("-u", "--nopentulum",
        dest="pentulum", default=True, action="store_false", 
        help="No Pentulum")
    parser.add_argument("-U", "--pentulum",
        dest="pentulum", default=True, action="store_true", 
        help="Use Pentulum")

    parser.add_argument("-p", "--pin", 
        dest="pin", default=LED_PIN, metavar='GPIO', type=int,
        help="GPIO Number")

    parser.add_argument("-i", "--invert",
        dest="invert", default=LED_INVERT, action="store_true", 
        help="Invert GPIO pin")

    parser.add_argument("-l", "--leds", 
        dest="leds", default=LED_COUNT, metavar='LEDS', type=int,
        help="Number of LEDs")

    parser.add_argument("-m", "--meridiem", 
        dest="meridiem", default=LED_MER, metavar='LED', type=int,
        help="Index of meridiem LED")

    parser.add_argument("-a", "--loglevel", 
                        dest="logLevel", default=0, type=int, metavar="LEVEL",
                        help="Set the maximum logging level - 0=no output, 1=error, 2=warning, 3=info, 4=debug, 5=ext.debug")

    parser.add_argument("-L", "--logfile", 
                        dest="logFile", default='Test', metavar="FILE",
                        help="Set FILE name for logging output")

    parser.add_argument("-q", "--quiet",
                        dest="verbose", default=True, action="store_false", 
                        help="don't print status messages to stdout")
    '''
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

