#!/usr/bin/python3

import feedparser   # pip install feedparser
import time, calendar
import sys
from argparse import ArgumentParser
from glob import glob
import html2text   # pip install html2text

import logging
l = logging.getLogger("piTelex." + __name__)

h = html2text.HTML2Text()
h.ignore_links = True
h.ignore_images = True
h.ignore_emphasis = True
h.ignore_tables = True

def split_newline_after(string, numchars):
    lines = []
    if numchars < 1:
        return string
    for i in range(0, len(string), numchars):
        lines.append(string[i:i+numchars])
    return '\n'.join(lines)

def formatted_write(output_path, rss_entry, visible_name, split_lines):
    #outfilenames = glob(output_path + "*.rsstx")
    #outfilename = output_path + "entry-%d.rsstx" % (len(outfilenames) + 1)
    outfilename = output_path + "NEWS-" + time.strftime("%Y-%m-%dT%H%M%S", time.localtime(calendar.timegm(rss_entry.published_parsed))) + ".rsstx"
    with open(outfilename, "a+") as outfile:
        summary = h.handle(rss_entry.summary)
        summary = summary.replace('\n', ' ')
        heading = visible_name + rss_entry.title
        heading = split_newline_after(heading, split_lines)
        summary = "    " + summary
        summary = split_newline_after(summary, split_lines)
        outfile.write(heading + "\n")
        outfile.write(summary + "\n")
        print(heading)
        print(summary)

if __name__ == "__main__":
    parser = ArgumentParser(description="Scan an RSS feed and write the summy to files in a telex-friendly format")
    #parser.add_argument("-u", "--feedurl", default="https://www.heise.de/rss/heise-atom.xml", help="RSS feed URL")
    parser.add_argument("-u", "--feedurl", default="https://www.faz.net/rss/aktuell/", help="RSS feed URL")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="timeout(seconds) between fetching feed updates")
    parser.add_argument("-f", "--forget-past", dest="forget_past", action='store_true', help="Don't look back")
    parser.add_argument("-p", "--ouput-path", dest="output_path", default="./", help="Output files path")
    parser.add_argument("-n", "--visible-name", dest="visible_name", default="", help="Prepend this string to each heading")
    parser.add_argument("-s", "--split-lines", type=int, dest="split_lines", default=60, help="Insert a linebreak after n characters")

    argv = sys.argv[1:]
    argp = parser.parse_args(argv)

    feed = feedparser.parse(argp.feedurl)

    if not argp.forget_past:
        for entry in feed.entries:
            formatted_write(argp.output_path, entry, argp.visible_name, argp.split_lines)

    known_ids = [entry.id for entry in feed.entries]

    while True:
        time.sleep(argp.timeout)
        feed = feedparser.parse(argp.feedurl)
        feed_ids = [entry.id for entry in feed.entries]
        new_ids = set(feed_ids) - set(known_ids)

        if new_ids is not None:
            entries = filter(lambda x: x.id in new_ids, feed.entries)
            for entry in entries:
                formatted_write(argp.output_path, entry, argp.visible_name, argp.split_lines)
            known_ids = known_ids + list(new_ids)
