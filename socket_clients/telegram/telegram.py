#!/usr/bin/env python3

# Telethon utility #pip install telethon
from telethon import TelegramClient, events
from telethon.tl.custom import Button
import yaml
import argparse
import re
import socket
import time

parser = argparse.ArgumentParser(
	description='A telegram bot that will take user input and send it to a socket', 
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

# Create the client and the session called session_master. We start the session as the Bot (using bot_token)
client = TelegramClient(
	config["telegram"]["session"], 
	config["telegram"]["api_id"], 
	config["telegram"]["api_hash"]).start(bot_token=config["telegram"]["bot_token"])

safe_senders = []


# Define the /start command
@client.on(events.NewMessage(pattern='(?i)/start')) 
async def start(event):
    sender = await event.get_sender()
    SENDER = sender.id
    text = "📇 271 🤖 ready\n" +\
        "\"<b>/print MESSAGE</b>\" → print a message on the telex\n"
    await client.send_message(SENDER, text, parse_mode="HTML")

# Print commen without data
@client.on(events.NewMessage(pattern='(?i)/print$')) 
async def start(event):
    sender = await event.get_sender()
    SENDER = sender.id
    text = "You need to precify a message to print\n" +\
        "\"<b>/print MESSAGE</b>\" → print a message on the telex\n"
    await client.send_message(SENDER, text, parse_mode="HTML")
  
### Print command with data
@client.on(events.NewMessage(pattern='(?i)/print\\s+(.*)')) 
async def quiz(event):
    # get the sender
    user = await event.get_sender()
    message = re.sub("\\/print\\s+", "", event.message.message, 1)

    text = 	"++++ New telegram message ++++\n"+\
    		"On   : {}\n"+\
    		"From : {} {} (@{})\n\n"+\
    		"{}\n"+\
    		"++++++++++++++++++++++++++++++\n\n"
    text = text.format(
    			event.message.date.astimezone(), 
    			user.first_name, 
    			user.last_name, 
    			user.username, 
    			message
    		)
    if config["watchdog"]["enabled"] :
	    tcp_client(config["watchdog"]["host"], config["watchdog"]["port"], "")
	    time.sleep(2)

    tcp_client(config["socket"]["host"], config["socket"]["port"], text)
    await client.send_message(user.id, "The following message was printed\n{}".format(text), parse_mode="HTML")
    return 

# (very) simple TCP client
def tcp_client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if verbose > 1:
        	print("Sending : {}".format(message))
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
    return

### MAIN
if __name__ == '__main__':
	if verbose :
		print("Bot started.")
	client.run_until_disconnected()
