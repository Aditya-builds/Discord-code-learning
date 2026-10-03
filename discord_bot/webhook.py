import asyncio
import logging
import sys

import aiohttp

from .config import DISCORD_WEBHOOK_URL, WEBHOOK_TIMEOUT

logger = logging.getLogger(__name__)
TIMEOUT = aiohttp.ClientTimeout(total=WEBHOOK_TIMEOUT)


async def get_webhook_channel_id(webhook_url: str | None = DISCORD_WEBHOOK_URL) -> int:
    # Ask Discord which channel this webhook posts into
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(webhook_url) as response:
            response.raise_for_status()
            data = await response.json()
            return int(data["channel_id"])


async def send_message(text: str, webhook_url: str | None = DISCORD_WEBHOOK_URL) -> bool:
    message = {
        "content": text,
        # Don't let the bot's reply ping @everyone/@here or roles
        "allowed_mentions": {"parse": ["users"]},
    }

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.post(webhook_url, json=message) as response:
            if response.status == 204:
                logger.info("Webhook message sent")
                return True
            logger.error("Webhook failed (%s): %s", response.status, await response.text())
            return False


if __name__ == "__main__":
    # Usage: python -m discord_bot.webhook "Hello from my code!"
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not DISCORD_WEBHOOK_URL:
        sys.exit("Set DISCORD_WEBHOOK_URL in your .env file first.")
    sent = asyncio.run(send_message(" ".join(sys.argv[1:]) or "Hello from my code!"))
    sys.exit(0 if sent else 1)
