#!/usr/bin/env python3

# inspired by: https://www.twilio.com/blog/how-to-build-a-slackbot-in-socket-mode-with-python

"""
To register the aoo go to:
https://api.slack.com/apps
* Create New APP button
    - From scratch
        - App name: <choose>
        - Workspace: <choose>
        - Creat App Button

* Features -> OAuth & Permissions
    - Add the following bot token scopes:
        - im:read
        - im:write
        - users.profile:read
        - char:write
* Settings -> Socket mode
    - Enable socket mode
        - Name the token <something>
        - Generate
        - The token you get is your SLACK_APP_TOKEN, save it
* Features -> Event subscriptions
    - Enable events
    - Subscribe to bot events
        - Add Bot user events
            - message.im
        - Save Changes
* Features -> App home
    - Show Tabs
        - Message Tab
            - (checkbox) Allow users to send Slash commands and messages from the messages tab
* Settings -> Basic Information
    - Display Information
        Save Changes
* Settings -> Install App
    - Install to Workspace
        - Either ask for approval or Allow
        - Save the two token (they can also be found in Aueth & Permissions)
            - THe Bot User OAuth token = SLACK_BOT_TOKEN


Or use the `manifest.yml` file in this directory, but then you steill need to:
* Features -> App home
    - Show Tabs
        - Message Tab
            - (checkbox) Allow users to send Slash commands and messages from the messages tab
* Settings -> Socket Mode
    - Toggle Enable Soclet Mode off then on
    - Save the token (this is you APP_TOKEN)

"""

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import yaml
import argparse
import socket
import time
import re
import datetime

parser = argparse.ArgumentParser(
    description='A Slack bot that will take user input and send it to a socket', 
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

app = App(token=config["slack"]["bot_token"])

@app.event("message")
def handle_message_events(body, say):
    user = app.client.users_profile_get(user=body["event"]["user"])

    # Expand user names
    body_text = body["event"]["text"]
    match = re.search("<@(.*?)>", body_text)
    while match is not None:
        muser = app.client.users_profile_get(user=match.group(1))
        body_text = re.sub(str(match.group(0)), "@{}".format(muser["profile"]["display_name"]),body_text)
        match = re.search("<@(.*?)>", body_text)
    text =  "++++ New slack message ++++\n"+\
        "On   : {}\n"+\
        "From : {} (@{})\n\n"+\
        "{}\n"+\
        "++++++++++++++++++++++++++++++\n\n"
    text = text.format(
                #time.gmtime(float(body["event"]["ts"])).astimezone(), 
                datetime.datetime.fromtimestamp(float(body["event"]["ts"])).strftime('%Y-%m-%d %H:%M:%S'),
                user["profile"]["real_name"], 
                user["profile"]["display_name"], 
                body_text
            )
    if config["watchdog"]["enabled"] :
        tcp_client(config["watchdog"]["host"], config["watchdog"]["port"], "")
        time.sleep(2)

    tcp_client(config["socket"]["host"], config["socket"]["port"], text)
    say("I sent the following message to the telex: \n ```\n{}```".format(text.strip()))
    return 

# (very) simple TCP client
def tcp_client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if verbose > 1:
            print("Sending : \n{}".format(message))
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
    return


if __name__ == "__main__":
    handler = SocketModeHandler(app, config["slack"]["app_token"])
    handler.start()
