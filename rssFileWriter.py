#!/bin/python3

import feedparser   # pip install feedparser
import time, calendar
import sys
from argparse import ArgumentParser
from glob import glob
import html2text   # pip install html2text

h = html2text.HTML2Text()
h.ignore_links = True
h.ignore_images = True
h.ignore_emphasis = True
h.ignore_tables = True

def formatted_write(output_path, rss_entry):
    #outfilenames = glob(output_path + "*.rsstx")
    #outfilename = output_path + "entry-%d.rsstx" % (len(outfilenames) + 1)
    outfilename = output_path + "NEWS-" + time.strftime("%Y-%m-%dT%H%M%S", time.localtime(calendar.timegm(rss_entry.published_parsed))) + ".rsstx"
    with open(outfilename, "w+") as outfile:
        # in case of HTML pull lever
        # text = html2text.html2text(html)
        summary = h.handle(rss_entry.summary)
        summary = summary.replace('\n', ' ')
        print(outfilename)
        print(rss_entry.title) 
        print("    " + summary + "\n")
        outfile.write(rss_entry.title + "\n")
        outfile.write("    " + summary )

if __name__ == "__main__":
    parser = ArgumentParser(description="Scan an RSS feed and write the summy to files in a telex-friendly format")
    #parser.add_argument("-u", "--feedurl", default="https://www.heise.de/rss/heise-atom.xml", help="RSS feed URL")
    parser.add_argument("-u", "--feedurl", default="https://www.faz.net/rss/aktuell/", help="RSS feed URL")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="timeout(seconds) between fetching feed updates")
    parser.add_argument("-f", "--forget-past", dest="forget_past", action='store_true', help="Don't look back")
    parser.add_argument("-p", "--ouput-path", dest="output_path", default="./", help="Output files path")

    argv = sys.argv[1:]
    argp = parser.parse_args(argv)

    feed = feedparser.parse(argp.feedurl)

    if not argp.forget_past:
        for entry in feed.entries:
            formatted_write(argp.output_path, entry)

    feed_ids = [entry.id for entry in feed.entries]

    while True:
        time.sleep(argp.timeout)
        new_feed = feedparser.parse(argp.feedurl)
        new_feed_ids = [entry.id for entry in new_feed.entries]
        new_ids = set(new_feed_ids) - set(feed_ids)

        if new_ids is not None:
            entries = filter(lambda x: x.id in new_ids, new_feed.entries)
            for entry in entries:
                formatted_write(argp.output_path, entry)
            feed = new_feed
            feed_ids = new_feed_ids
