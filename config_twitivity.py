# configure.py

from twitivity import Activity

account_activity = Activity()
print(account_activity.register_webhook("https://my.webhookrelay.com/v1/webhooks/INSERT_WEBHOOK_HERE").text)
print(account_activity.subscribe().text)
