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
import txDevMCP

import time, datetime
import threading
import os, os.path
import sys
import logging
l = logging.getLogger("piTelex." + __name__)
import logging.handlers
import traceback

#######
# definitions and configuration


#######
# global variables

DEVICES = []
TIME_20HZ = time.time()
TIME_DELAY = None
ERRLOG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "error_log")
ERRLOG_LEVEL = logging.INFO
#ERRLOG_LEVEL = logging.DEBUG

#######
# -----


# =====

class MonthlyRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Custom Handler for a monthly rotated log file. Implementation based on
    original Python source code (CPython's Lib/logging/handlers.py).
    """
    def __init__(self, filename, mode='a', encoding=None):
        # Disable maxBytes to ensure rolling over only on month change
        # Disable dbackupCount because it's not used
        # Disable delay to simplify overridden methods
        super().__init__(filename, mode=mode, maxBytes=0, backupCount=0, encoding=encoding, delay=False)

        # Initialise last year-month-stamp
        self.last_year_month = datetime.datetime.now().strftime("%Y-%m")

    def shouldRollover(self, record):
        current_year_month = datetime.datetime.now().strftime("%Y-%m")
        if self.last_year_month == current_year_month:
            return 0
        else:
            return 1

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        dfn = self.rotation_filename(self.baseFilename + "_" + self.last_year_month)
        self.last_year_month = datetime.datetime.now().strftime("%Y-%m")
        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)
        self.stream = self._open()

    def rotate(self, source, dest):
        if os.path.exists(source):
            os.rename(source, dest)

def init_error_log():
    """
    Initialise error logging, i.e. create the root logger.

    This is different from the log module, which implements a communication
    trace log (i.e. it logs the data read from all piTelex modules).

    Install handlers for uncaught exceptions.

    All piTelex modules should initialise their logging like so:

    >>> import logging
    >>> l = logging.getLogger("piTelex." + __name__)

    Calling l.warning et al. funnels all messages into the same log file of the
    root logger ("piTelex").
    """
    logger = logging.getLogger("piTelex")
    logger.setLevel(ERRLOG_LEVEL)
    try:
        os.mkdir(ERRLOG_PATH)
    except FileExistsError:
        pass
    handler = MonthlyRotatingFileHandler(filename = os.path.join(ERRLOG_PATH, "piTelex-errors.log"))

    handler.setLevel(ERRLOG_LEVEL)
    formatter = logging.Formatter('%(asctime)s %(name)s [%(levelname)s]: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    sys.excepthook = excepthook
    sys.unraisablehook = unraisablehook # Works from Python 3.8
    threading.excepthook = threading_excepthook

    # Log application start
    from txDevLog import find_rev
    rev = "(ERR)"
    try:
        rev = find_rev()
    finally:
        logger.info("===== piTelex rev " + rev)

def excepthook(etype, value, tb):
    l.critical("".join(traceback.format_exception(etype, value, tb)))

def unraisablehook(unraisable):
    excepthook(unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback)

def threading_excepthook(args):
    l.critical("Exception in Thread {}".format(args.thread))
    excepthook(args.exc_type, args.exc_value, args.exc_traceback)

def init():
    global DEVICES

    #mode = txConfig.CFG['mode'].strip()

    ctrl = txDevMCP.TelexMCP(**txConfig.CFG)
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

        #if dev_param['type'] == 'telnet':
        #    import txDevTelnetSrv
        #    srv = txDevTelnetSrv.TelexTelnetSrv(**dev_param)
        #    DEVICES.append(srv)

        if dev_param['type'] == 'i-Telex':
            import txDevITelexClient
            srv = txDevITelexClient.TelexITelexClient(**dev_param)
            DEVICES.append(srv)

            if dev_param['port'] > 0:
                import txDevITelexSrv
                srv = txDevITelexSrv.TelexITelexSrv(**dev_param)
                DEVICES.append(srv)

        if dev_param['type'] == 'news':
            import txDevNews
            news = txDevNews.TelexNews(**dev_param)
            DEVICES.insert(0,news)

        if dev_param['type'] == 'IRC':
            import txDevIRC
            news = txDevIRC.TelexIRC(**dev_param)
            DEVICES.insert(0,news)

        if dev_param['type'] == 'REST':
            import txDevREST
            news = txDevREST.TelexREST(**dev_param)
            DEVICES.insert(0,news)

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
    logging.shutdown()

# =====

def loop():
    global TIME_20HZ, TIME_DELAY

    if TIME_DELAY and time.time() > TIME_DELAY:
        TIME_DELAY = None

    if not TIME_DELAY:
        for in_device in DEVICES:
            c = in_device.read()
            if c:
                l.debug("read {!r} from {!r}".format(c, in_device))
                for out_device in DEVICES:
                    if out_device != in_device:
                        l.debug("writing {!r} to {!r}".format(c, out_device))
                        ret = out_device.write(c, in_device.id)
                        l.debug("writing returned {!r}".format(ret))
                        # Evaluate write return value:
                        if ret is not None:
                            if isinstance(ret, float):
                                # if it's a float, wait for this time in s
                                TIME_DELAY = time.time() + ret
                            else:
                                # else, stop writing to other devices (discard
                                # data)
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
    init_error_log()
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

