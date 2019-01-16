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

        if dev_param['type'] == 'itelex':
            import txITelexClient
            srv = txITelexClient.TelexITelexClient(**dev_param)
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
    
    #test()
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

# =====

def test():
    import serial
    #https://telexforum.de/viewtopic.php?f=29&t=485

    import socket

    HOST = 'sonnibs.no-ip.org'  # The server's hostname or IP address    or itelex.teleprinter.net or 176.52.197.242
    PORT = 11811        # The port used by the server

    number = '97475'

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        qry = bytearray('q{}\r\n'.format(number.strip()), "ASCII")
        s.sendall(qry)
        data = s.recv(1024)

    data = data.decode('ASCII')
    lines = data.split('\r\n')

    if len(lines) < 2 or lines[0] != 'ok':
        print('fail', repr(data))

    print('Received', repr(data))




    import socket

    HOST = '89.182.87.147'  # The server's hostname or IP address
    PORT = 134        # The port used by the server

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.settimeout(0.5)
        qry = bytearray([7, 1, 1])
        s.sendall(qry)

        while 1:
            try:
                data = s.recv(1024)
                if not data:
                    print('Error')
                
                if data[0] == 0:   # Heartbeat
                    print('Heartbeat', repr(data))
                    pass

                elif data[0] == 1:   # Direct Dial
                    print('Direct Dial', repr(data))
                    pass

                elif data[0] == 2:   # Baudot data
                    print('Baudot data', repr(data))
                    pass

                elif data[0] == 3:   # End
                    print('End', repr(data))
                    pass

                elif data[0] == 4:   # Reject
                    print('Reject', repr(data))
                    pass

                elif data[0] == 6:   # Acknowledge
                    print('Acknowledge', repr(data))
                    pass

                elif data[0] == 7:   # Version
                    print('Version', repr(data))
                    pass

                elif data[0] == 8:   # Self test
                    print('Self test', repr(data))
                    pass

                elif data[0] == 9:   # Remote config
                    print('Remote config', repr(data))
                    pass

                else:
                    print('Other', repr(data))
                    pass

            except socket.timeout:
                print('Timeout')

            except socket.error:
                print('Error')
                break










    s = serial.serial_for_url('socket://89.182.87.147:134', timeout=10)

    qry = bytearray([7, 1, 1])
    s.write(qry)

    try:
        while s.is_open:
            l = s.in_waiting
            if l:
                data = bytearray()
                key = s.read()
                l = s.read()
                if l:
                    for i in range(int(l[0])):
                        d = s.read()
                        data += d
                print (key, l, data)
    except Exception as e:
        pass

    pass













    number = '97475'

    s = serial.serial_for_url('socket://sonnibs.no-ip.org:11811')

    qry = bytearray('q{}\r\n'.format(number.strip()), "ASCII")
    s.write(qry)

    ans = ''
    try:
        while s.is_open:
            l = s.in_waiting
            x = s.read(l)
            ans += x.decode('ASCII')
    except:
        pass

    anss = ans.split('\r\n')

    print(anss)
    pass

#######

if __name__== "__main__":
    main()

