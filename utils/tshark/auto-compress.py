#!/usr/bin/env python3

"""
auto-compress.py: tshark compression helper

This script is intended to be run alongside a tshark instance called with -b
(multiple files mode), which captures network traffic and creates new capture
files according to set criteria (time elapsed or size). This script will

- listen for directory changes;
- if there is one, enumerate all uncompressed files matching the configured pattern;
- compress them, except the most recent one, which is probably still being
  written to by tshark;
- and finally delete the uncompressed original.
"""

TSHARK_PATH = "/home/pi/piTelex/tshark"
PATTERN = "pitelex-cont-*_*_*.pcapng"

import time
import logging
import gzip
import shutil
import os
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, PatternMatchingEventHandler
from glob import glob

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

def get_files_to_compress():
    """
    Return all files matching the set pattern.
    """
    files = sorted(glob(os.path.join(TSHARK_PATH, PATTERN)))
    del files[-1]
    return files

def compress_file(filename):
    """
    Compress the given file if no compressed copy exists already, and delete
    the uncompressed copy.
    """
    try:
        open(filename+".gz", mode='rb')
    except FileNotFoundError:
        with open(filename, mode='rb') as f_in:
            with gzip.open(filename+".gz", mode='wb', compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
                return True
    else:
        return False

def on_modified_tshark_dir(event):
    """
    The directory containing tshark capture files has been modified. Among
    others, this is the case when tshark creates a new file.

    So enumerate all uncompressed files in question and compress them, except
    the last one which is probably still being written to by tshark.
    """
    files = get_files_to_compress()
    logging.info("Directory change; %d files to compress" % len(files))
    for f in files:
        logging.info("Compressing file %s" % f)
        if compress_file(f):
            logging.info("Deleting original file")
            os.remove(f)
        else:
            logging.info("Compressed file exists, skipping")
        logging.info("Done.")

if __name__ == "__main__":
    observer = Observer()
    #event_handler = LoggingEventHandler()
    #observer.schedule(event_handler, TSHARK_PATH, recursive=True)
    event_handler = PatternMatchingEventHandler(patterns=[TSHARK_PATH])
    event_handler.on_modified = on_modified_tshark_dir
    observer.schedule(event_handler, TSHARK_PATH)
    observer.start()
    try:
        while True:
            time.sleep(600)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

