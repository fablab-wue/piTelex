#!/usr/bin/python3
"""
testTelex for RPi Zero W or PC
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "0.0.2"

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

#import log
#def LOG(text:str, level:int=3):
#    log.LOG('\033[0;30;47m '+text+' \033[0m', level)

#######
# global variables

DEVICES = []

# Path where this file is stored
try:
    OUR_PATH = os.path.dirname(os.path.realpath(__file__))
except NameError:
    # If __file__ is not defined, fall back to working directory; should be
    # close enough.
    OUR_PATH = os.getcwd()

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

def find_rev() -> str:
    """
    Try finding out the git commit id and return it.
    """
    import subprocess
    result = subprocess.run(["git", "log", "--oneline", "-1"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return result.stdout.decode("utf-8", errors="replace").strip()

def init_error_log(log_path,log_lvl):
    """
    Initialise error logging, i.e. create the root logger. It saves all logged
    information in a monthly rotating file inside the path given. If the latter
    is relative, it's interpreted relative to where this Python file is stored.

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
    logger.setLevel(log_lvl) # Log level of this root logger
    
    if not os.path.isabs(log_path):
        log_path = os.path.join(OUR_PATH, log_path)
    try:
        os.mkdir(log_path)
    except FileExistsError:
        pass
    handler = MonthlyRotatingFileHandler(filename = os.path.join(log_path, "piTelex-errors.log"))

    handler.setLevel(logging.DEBUG) # Upper bounds for log level of all loggers
    formatter = logging.Formatter('%(asctime)s %(name)s [%(levelname)s]: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    sys.excepthook = excepthook
    sys.unraisablehook = unraisablehook # Works from Python 3.8
    threading.excepthook = threading_excepthook

    # Log application start
    try:
        rev = find_rev()
    except:
        pass
    else:
        logger.info("===== piTelex rev " + rev)

def excepthook(etype, value, tb):
    to_log = "".join(traceback.format_exception(etype, value, tb))
    l.critical(to_log)
    print(to_log)

def unraisablehook(unraisable):
    excepthook(unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback)

def threading_excepthook(args):
    l.critical("Exception in Thread {}".format(args.thread))
    excepthook(args.exc_type, args.exc_value, args.exc_traceback)

def init():
    global DEVICES

    ctrl = txDevMCP.TelexMCP(**txConfig.CFG)
    DEVICES.append(ctrl)

    # Iterate over configuration items, create configured instances and add
    # them to DEVICES.
    for dev_name, dev_param in txConfig.CFG['devices'].items():
        if not dev_param.get('enable', False):
            continue

        dev_param['name'] = dev_name

        if dev_param['type'] == 'screen':
            import txDevScreen
            screen = txDevScreen.TelexScreen(**dev_param)
            DEVICES.append(screen)

        elif dev_param['type'] == 'ED1000':
            import txDevED1000SC
            serial = txDevED1000SC.TelexED1000SC(**dev_param)
            DEVICES.append(serial)

        elif dev_param['type'] == 'CH340TTY':
            import txDevCH340TTY
            serial = txDevCH340TTY.TelexCH340TTY(**dev_param)
            DEVICES.append(serial)

        elif dev_param['type'] == 'terminal':
            import txDevTerminal
            serial = txDevTerminal.TelexTerminal(**dev_param)
            DEVICES.append(serial)

        elif dev_param['type'] == 'RPiTTY':
            import txDevRPiTTY
            serial = txDevRPiTTY.TelexRPiTTY(**dev_param)
            DEVICES.append(serial)

        elif dev_param['type'] == 'RPiCtrl':
            import txDevRPiCtrl
            ctrl = txDevRPiCtrl.TelexRPiCtrl(**dev_param)
            DEVICES.append(ctrl)

        #elif dev_param['type'] == 'telnet':
        #    import txDevTelnetSrv
        #    srv = txDevTelnetSrv.TelexTelnetSrv(**dev_param)
        #    DEVICES.append(srv)

        elif dev_param['type'] == 'i-Telex':
            import txDevITelexClient
            srv = txDevITelexClient.TelexITelexClient(**dev_param)
            DEVICES.append(srv)

            if "centralex" in dev_param:
                import txDevITelexCentralex
                srv = txDevITelexCentralex.TelexITelexCentralex(**dev_param)
                DEVICES.append(srv)

            elif dev_param['port'] > 0:
                import txDevITelexSrv
                srv = txDevITelexSrv.TelexITelexSrv(**dev_param)
                DEVICES.append(srv)

        elif dev_param['type'] == 'news':
            import txDevNews
            news = txDevNews.TelexNews(**dev_param)
            DEVICES.insert(0,news)

        #elif dev_param['type'] == 'twitter':
        #    import txDevTwitter
        #    twitter = txDevTwitter.TelexTwitter(**dev_param)
        #    DEVICES.append(twitter)

        #elif dev_param['type'] == 'twitterV2':
        #    import txDevTwitterV2
        #    twitterV2 = txDevTwitterV2.TelexTwitterV2(**dev_param)
        #    DEVICES.append(twitterV2)

        elif dev_param['type'] == 'rss' :
            import txDevRSS
            rss = txDevRSS.TelexRSS(**dev_param)
            DEVICES.append(rss)

        elif dev_param['type'] == 'IRC':
            import txDevIRC
            news = txDevIRC.TelexIRC(**dev_param)
            DEVICES.insert(0,news)

        elif dev_param['type'] == 'REST':
            import txDevREST
            news = txDevREST.TelexREST(**dev_param)
            DEVICES.insert(0,news)

        elif dev_param['type'] == 'eliza':
            import txDevEliza
            eliza = txDevEliza.TelexEliza(**dev_param)
            DEVICES.append(eliza)

        elif dev_param['type'] == 'archive':
            import txDevArchive
            archive = txDevArchive.TelexArchive(**dev_param)
            DEVICES.append(archive)

        elif dev_param['type'] == 'shellcmd':
            import txDevShellCmd
            module = txDevShellCmd.TelexShellCmd(**dev_param)
            DEVICES.append(module)

        elif dev_param['type'] == 'log':
            import txDevLog
            log = txDevLog.TelexLog(**dev_param)
            DEVICES.insert(0,log)

        elif dev_param['type'] == 'KeyPad':
            import txDevKeyPad
            keypad = txDevKeyPad.TelexKeyPad(**dev_param)
            DEVICES.append(keypad)

        else:
            l.warning("Unknown module type in configuration, section {!r}: {!r}".format(dev_name, dev_param['type']))


# =====

def exit():
    global DEVICES

    for device in DEVICES:
        try:
            device.exit()
            del device
        except Exception as e:
            pass
    DEVICES = []
    logging.shutdown()
    return
    # Comment out the return above to view non-terminating threads
    while True:
        for t, stack in sys._current_frames().items():
            l.info("Thread: {}".format(t))
            [l.info(i) for i in traceback.format_stack(stack)]
        time.sleep(5)

# =====

def process_data():
    new_data = False

    for in_device in DEVICES:
        try:
            c = in_device.read()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            l.warning("Uncaught Exception in {}.read(): {!r}".format(in_device.id, e))
        if c:
            new_data = True
            l.debug("read {!r} from {!r}".format(c, in_device))
            for out_device in DEVICES:
                if out_device != in_device:
                    l.debug("writing {!r} to {!r}".format(c, out_device))
                    try:
                        ret = out_device.write(c, in_device.id)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except Exception as e:
                        l.warning("Uncaught Exception in {}.write({!r}), {!r}: {!r}".format(out_device.id, c, in_device.id, e))
                    if ret:
                        l.debug("writing returned {!r}".format(ret))
                        break   # stop writing to other devices (discard data)

    return new_data

# -----

def process_idle():
    for device in DEVICES:
        try:
            device.idle()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            l.warning("Uncaught Exception in {}.idle(): {!r}".format(device.id, e))

# -----

def process_idle20Hz():
    for device in DEVICES:
        try:
            device.idle20Hz()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            l.warning("Uncaught Exception in {}.idle20Hz(): {!r}".format(device.id, e))

# -----

def process_idle2Hz():
    for device in DEVICES:
        try:
            device.idle2Hz()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            l.warning("Uncaught Exception in {}.idle2Hz(): {!r}".format(device.id, e))

# =====

def main():
    txConfig.load()

    LOGLVL = { 'NOTSET' : 0 , 'DEBUG' : 10 , 'INFO' : 20 , 'WARN' : 30 , 'ERROR' : 40 , 'CRITICAL' : 50 }
    errorlog_path = txConfig.CFG.get('errorlog_path', 'error_log')
    errorlog_level = txConfig.CFG.get('errorlog_level', 'INFO')
    errorlog_level = errorlog_level.strip()
    errorlog_level = errorlog_level.upper()

    if errorlog_level in LOGLVL :
        loglvl = LOGLVL[errorlog_level]
    else:
        print('\n unknown loglevel: ',errorlog_level,', set to INFO.')       
        loglvl = logging.INFO

    init_error_log(errorlog_path,loglvl)

    #test()   # for debug only
    init()

    print('\n\033[0;30;47m -=TELEX=- \033[0m\n')

    time_2Hz = time.monotonic()
    time_20Hz = time.monotonic()
    time_200Hz = time.monotonic()
    sleep_time = 0.001

    try:
        while True:
            time_act = int(time.monotonic() * 1000)   # time in ms

            new_data = process_data()
            if new_data:
                sleep_time = 0.0001

            if (time_act - time_200Hz) >= 5:
                time_200Hz = time_act
                process_idle()

                if (time_act - time_20Hz) >= 50:
                    time_20Hz = time_act
                    process_idle20Hz()

                    if (time_act - time_2Hz) >= 500:
                        time_2Hz = time_act
                        process_idle2Hz()

            time.sleep(sleep_time)   # update with max ??? Hz
            if sleep_time < 0.010:
                sleep_time += 0.0001

    except (KeyboardInterrupt, SystemExit):
        l.info('Exit by Keyboard')

    finally:
        exit()

# =====

def test():
    pass

#######

if __name__== "__main__":
    main()

