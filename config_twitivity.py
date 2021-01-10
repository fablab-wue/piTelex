# config_twitivity.py
import sys
import argparse

from twitivity import Activity

parser = argparse.ArgumentParser(description='Register, delete or refresh webhooks')

parser.add_argument('--delete', action='store_true', help='delete existing webhooks')
parser.add_argument('--refresh', action='store_true', help='refresh existing webhooks')
parser.add_argument('--add', metavar='URL',default="", help='add webhook')

args = parser.parse_args()


url = ""
account_activity = Activity()
hooks=account_activity.webhooks()
print(hooks)
for hook in  hooks['environments'][0]['webhooks']:
  id=hook['id']
  url=hook['url']
  print(id)
  if args.refresh:
    print(account_activity.refresh(id))
  if args.delete:
    print(account_activity.delete(id))
if args.add != "":
  if url == "":
    url = args.add
  new_hook=account_activity.register_webhook(url)
  print(new_hook)
  new_id=new_hook['id']
  print(new_id)
  print(account_activity.subscribe())
