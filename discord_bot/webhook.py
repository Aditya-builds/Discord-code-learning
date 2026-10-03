import sys

import requests

from .config import DISCORD_WEBHOOK_URL


def get_webhook_channel_id(webhook_url=DISCORD_WEBHOOK_URL):
    # Ask Discord which channel this webhook posts into
    response = requests.get(webhook_url, timeout=10)
    response.raise_for_status()
    return int(response.json()["channel_id"])


def send_message(text, webhook_url=DISCORD_WEBHOOK_URL):
    message = {
        "content": text,
        # Don't let the bot's reply ping @everyone/@here or roles
        "allowed_mentions": {"parse": ["users"]},
    }

    response = requests.post(webhook_url, json=message, timeout=10)

    if response.status_code == 204:
        print("Message sent successfully!")
        return True
    print(f"Failed to send message. Status code: {response.status_code}")
    print(response.text)
    return False


if __name__ == "__main__":
    # Usage: python -m discord_bot.webhook "Hello from my code!"
    if not DISCORD_WEBHOOK_URL:
        sys.exit("Set DISCORD_WEBHOOK_URL in your .env file first.")
    send_message(" ".join(sys.argv[1:]) or "Hello from my code!")
