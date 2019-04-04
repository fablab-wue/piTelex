#!/usr/bin/python3
"""
testTelex for RPi Zero W or PC
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txConfig
import txDevController

import time
import threading
from argparse import ArgumentParser

#######
# definitions and configuration


#######
# global variables

DEVICES = []
TIME_20HZ = time.time()

#######
# -----


# =====

def init():
    global DEVICES

    #mode = txConfig.CFG['mode'].strip()

    ctrl = txDevController.TelexController(**txConfig.CFG)
    DEVICES.append(ctrl)

    for dev_name, dev_param in txConfig.CFG['devices'].items():
        if not dev_param.get('enable', False):
            continue
        
        dev_param['name'] = dev_name
        #if 'mode' not in dev_param:
        #    dev_param['mode'] = mode

        if dev_param['type'] == 'screen':
            import txDevScreen
            screen = txDevScreen.TelexScreen(**dev_param)
            DEVICES.append(screen)

        if dev_param['type'] == 'CH340TTY':
            import txDevCH340TTY
            serial = txDevCH340TTY.TelexCH340TTY(**dev_param)
            DEVICES.append(serial)

        if dev_param['type'] == 'RPiTTY':
            import txDevRPiTTY
            serial = txDevRPiTTY.TelexRPiTTY(**dev_param)
            DEVICES.append(serial)

        if dev_param['type'] == 'ED1000':
            import txDevED1000SC
            serial = txDevED1000SC.TelexED1000SC(**dev_param)
            DEVICES.append(serial)

        if dev_param['type'] == 'telnet':
            import txDevTelnetSrv
            srv = txDevTelnetSrv.TelexTelnetSrv(**dev_param)
            DEVICES.append(srv)

        if dev_param['type'] == 'i-Telex':
            import txDevITelexClient
            srv = txDevITelexClient.TelexITelexClient(**dev_param)
            DEVICES.append(srv)

            if dev_param['port'] > 0:
                import txDevITelexSrv
                srv = txDevITelexSrv.TelexITelexSrv(**dev_param)
                DEVICES.append(srv)

        if dev_param['type'] == 'eliza':
            import txDevEliza
            eliza = txDevEliza.TelexEliza(**dev_param)
            DEVICES.append(eliza)

        if dev_param['type'] == 'log':
            import txDevLog
            log = txDevLog.TelexLog(**dev_param)
            DEVICES.insert(0,log)

# =====

def exit():
    global DEVICES
    
    for device in DEVICES:
        device.exit()
        del device
    DEVICES = []

# =====

def loop():
    global TIME_20HZ

    for in_device in DEVICES:
        c = in_device.read()
        if c:
            for out_device in DEVICES:
                if out_device != in_device:
                    if out_device.write(c, in_device.id):
                        break
    
    for device in DEVICES:
        device.idle()

    time_act = time.time()
    if (time_act - TIME_20HZ) >= 0.05:
        TIME_20HZ = time_act
        for device in DEVICES:
            device.idle20Hz()

    return

# =====

def main():
    txConfig.load()
    
    #test()
    init()

    print('\033[2J-=TELEX=-')

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

# =====

def test():
    pass

#######

if __name__== "__main__":
    main()

