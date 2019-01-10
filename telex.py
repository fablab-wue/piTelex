#!/usr/bin/python
"""
testTelex for RPi Zero W or PC
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txConfig
import txController

import time
import threading
from argparse import ArgumentParser

#######
# definitions and configuration


#######
# global variables

DEVICES = []

#######
# -----


# =====

def init():
    global DEVICES

    ctrl = txController.TelexController(txConfig.CFG['wru_id'].strip())
    DEVICES.append(ctrl)

    for dev_name, dev_param in txConfig.CFG['devices'].items():
        dev_param['name'] = dev_name
        
        if dev_param['type'] == 'screen':
            import txScreen
            screen = txScreen.TelexScreen(**dev_param)
            DEVICES.append(screen)

        if dev_param['type'] == 'tty':
            import txSerial
            serial = txSerial.TelexSerial(**dev_param)
            DEVICES.append(serial)

        if dev_param['type'] == 'gpio':
            import txPiGPIO
            serial = txPiGPIO.TelexPiGPIO(**dev_param)
            DEVICES.append(serial)

        if dev_param['type'] == 'ed1000':
            import txED1000TxOnly
            serial = txED1000TxOnly.TelexED1000TxOnly(**dev_param)
            DEVICES.append(serial)

        if dev_param['type'] == 'term':
            import txTermSrv
            srv = txTermSrv.TelexTermSrv(**dev_param)
            DEVICES.append(srv)

        if dev_param['type'] == 'eliza':
            import txEliza
            eliza = txEliza.TelexEliza(**dev_param)
            DEVICES.append(eliza)

# =====

def exit():
    pass

# =====

def loop():
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
    txConfig.load()
    
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

