#!/usr/bin/python
"""
testTelex for RPi Zero W
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import TelexSerial
import Screen

import time
from argparse import ArgumentParser

#######
# definitions and configuration


#######
# global variables

args = None
screen = None
telex = None
i_telex = None

#######
# -----


# =====

def init():
    global args, screen, telex

    #PI.set_mode(GPIO_BUTTON, pigpio.INPUT)
    #PI.set_pull_up_down(GPIO_BUTTON, pigpio.PUD_UP)

    screen = Screen.Screen()

    telex = TelexSerial.TelexSerial(args.id.strip(), args.tty.strip())

# =====

def exit():
    global args, screen, telex

    pass

# =====

def loop():
    global args, screen, telex, i_telex

    if screen:
        c = screen.read()
        if c:
            if telex:
                telex.write(c)
            if i_telex:
                i_telex.write(c)
    
    if telex:
        c = telex.read()
        if c:
            if screen:
                screen.write(c)
            if i_telex:
                i_telex.write(c)
    
    if i_telex:
        c = i_telex.read()
        if c:
            if telex:
                telex.write(c)
            if screen:
                screen.write(c)

    return

# =====

def main():
    global args

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
    args = parser.parse_args()

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

