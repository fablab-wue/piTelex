#!/bin/python3

import feedparser
import time
import sys
from argparse import ArgumentParser

if __name__ == "__main__":
    parser = ArgumentParser(description="Scan an RSS feed and write the contens to a file in a telex-friendly format")
    parser.add_argument("-u", "--feedurl", default="https://www.presseportal.de/rss/netzwelt.rss2", help="RSS feed URL")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="timeout(seconds) between fetching feed updates")
    parser.add_argument("-f", "--forget-past", dest="forget_past", action='store_true', help="Don't look back")
    parser.add_argument("-o", "--outfile", default="outfile.txt", help="Output filename")

    argv = sys.argv[1:]
    argp = parser.parse_args(argv)

    outfile = open(argp.outfile, "a")
    feed = feedparser.parse(argp.feedurl)
    feed_ids = [entry.id for entry in feed.entries]

    if not argp.forget_past:
        for entry in feed.entries:
            print(entry.title)
            print(entry.summary)
            #outfile.flush()

    while True:
        time.sleep(argp.timeout)
        new_feed = feedparser.parse(argp.feedurl)
        new_feed_ids = [entry.id for entry in new_feed.entries]
        new_ids = set(new_feed_ids) - set(feed_ids)

        if new_ids is not None:
            for id in new_ids:
                print(new_feed.entries[id].title)
                print(new_feed.entries[id].summary)
                #outfile.flush()
            feed = new_feed
            feed_ids = new_feed_ids
