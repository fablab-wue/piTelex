#!/usr/bin/env python3


"""
"""


import yaml
import argparse
import socket
import time
import re
import datetime
import openai
from textwrap import fill

# (very) simple TCP client
def tcp_client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if verbose > 1:
            print("Sending : \n{}".format(message))
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='A chatGPT bot that will converse with a socket (for use with txDevSocket.py)',
        allow_abbrev=True
    )
    parser.add_argument('-c', '--config', type=str, metavar="config.yml", default="config.yml", help="Configuration file")

    parser.add_argument('-v', '--verbose', action="count", default=1, help="Be (more) verbose" )
    parser.add_argument('-q', '--quiet', action="store_true", default=False, help="Be quiet, only output errors")

    args = parser.parse_args()

    verbose = args.verbose
    if args.quiet :
        verbose = 0

    ### Read config ###
    if verbose > 1:
        print("Loading config file {}".format(args.config))
    with open(args.config, 'r') as file:
        config = yaml.safe_load(file)

    openai. api_key = config["openai"]["api_key"]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((config["socket"]["host"], config["socket"]["port"]))
    lastuse = 0

    buffer = ""
    messages = [ {"role": "system", "content": config["openai"]["prompt"]} ]
    chat = openai.chat.completions.create(
        model=config["openai"]["model"], messages=messages, stream=False
    )
    content = chat.choices[0].message.content
    messages.append({ "role" : "assistant", "content" : content})
    if config.get("welcome", None) :
        if config["watchdog"]["enabled"] :
            tcp_client(config["watchdog"]["host"], config["watchdog"]["port"], "")
            time.sleep(2)
        sock.sendall(bytes("{}\n\n".format(config["welcome"]), 'utf-8'))


    timeout = time.time() + config["openai"]["timeout"]
    while True:
        data = sock.recv(1024)
        if data :
            if config["watchdog"]["enabled"] :
                tcp_client(config["watchdog"]["host"], config["watchdog"]["port"], "")
            if time.time() < timeout :
                timeout = time.time() + config["openai"]["timeout"]
            else:
                messages = [ {"role": "system", "content": config["openai"]["prompt"]} ]
                chat = openai.chat.completions.create(
                    model=config["openai"]["model"], messages=messages, stream=False
                )
                content = chat.choices[0].message.content
                messages.append({ "role" : "assistant", "content" : content})
            text = "{}{}".format(buffer,data.decode('utf-8', 'replace').replace('\ufffd','?'))
            lines = text.split("\r")
            question = ""
            if len(lines) > 1 :
                question = lines[0].strip()
                buffer = "".join(lines[1:])
            elif text.endswith("\r") or text.endswith("\n") :
                question = text
                buffer = ""
            else:
                buffer = text
            if question :
                if question.strip() != "" :
                    if config["watchdog"]["enabled"] :
                        tcp_client(config["watchdog"]["host"], config["watchdog"]["port"], "")
                    time.sleep(2)
                    sock.sendall(bytes("---\n", 'utf-8'))
                    messages.append({"role": "user", "content": question})
                    chat = openai.chat.completions.create(
                        model=config["openai"]["model"], messages=messages, stream=False
                    )
                    content = chat.choices[0].message.content
                    messages.append({ "role" : "assistant", "content" : content})
                    content = fill(content, width=60)
                    sock.sendall(bytes(content, 'utf-8'))
                    sock.sendall(bytes("\n\n", 'utf-8'))

