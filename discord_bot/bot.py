import logging

import anthropic
import discord

from . import config, webhook
from .claude_chat import ClaudeChat
from .storage import BotStorage, make_entry
from .text import split_message, strip_mention

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)
storage = BotStorage(config.STATE_FILE, config.MESSAGES_FILE, config.CONVERSATIONS_FILE)
chat = ClaudeChat(storage=storage)

# The webhook can only post in one channel; looked up once in on_ready
webhook_channel_id: int | None = None


async def find_webhook_channel() -> None:
    global webhook_channel_id
    if not config.DISCORD_WEBHOOK_URL:
        logger.info("No DISCORD_WEBHOOK_URL set; replying as the bot everywhere")
        return
    try:
        webhook_channel_id = await webhook.get_webhook_channel_id()
    except Exception as e:
        logger.warning("Couldn't reach the webhook (%s); replying as the bot instead", e)
        return
    # Other channels get normal bot replies, so say where the webhook applies
    channel = client.get_channel(webhook_channel_id)
    if channel is None:
        logger.warning("Webhook posts to channel %s, which this bot can't see", webhook_channel_id)
    else:
        logger.info("Replying through the webhook in #%s; as the bot elsewhere", channel)


async def sync_missed_messages() -> None:
    # 1. Get the last time the bot was online
    last_seen = storage.get_last_seen()
    if last_seen:
        logger.info("Fetching missed messages since %s...", last_seen)
    else:
        logger.info("First run! Fetching recent history...")

    # On first run there's no timestamp to stop at, so only look at recent messages
    fetch_limit = config.HISTORY_FETCH_LIMIT if last_seen else 100

    # 2. Loop through all channels the bot can see
    for guild in client.guilds:
        for channel in guild.text_channels:
            # Check if bot has permission to read history
            if not channel.permissions_for(guild.me).read_message_history:
                continue

            try:
                # 3. Fetch messages sent after `last_seen` (discord.py pages through them for us)
                async for message in channel.history(limit=fetch_limit, after=last_seen):
                    if message.author == client.user or client.user not in message.mentions:
                        continue

                    entry = make_entry(message, strip_mention(message.content, client.user.id))
                    storage.add_message(entry, save=False)
                    logger.info("Recovered missed message: %s", entry)

            except discord.Forbidden:
                logger.warning("Missing permissions to read history in #%s", channel.name)
            except Exception:
                logger.exception("Error reading #%s", channel.name)

    # 4. Save the new messages and update the last_seen time
    storage.save_messages()
    storage.update_last_seen()


async def send_reply(message: discord.Message, reply_text: str) -> None:
    # Split to respect Discord's 2000-character limit
    if message.channel.id == webhook_channel_id:
        # Reply through the webhook, tagging who asked
        for chunk in split_message(f"{message.author.mention} {reply_text}"):
            if not await webhook.send_message(chunk):
                await message.channel.send(chunk)  # Fall back to the bot if the webhook fails
        return

    chunks = split_message(reply_text)
    await message.reply(chunks[0], mention_author=False)
    for chunk in chunks[1:]:
        await message.channel.send(chunk)


@client.event
async def on_ready() -> None:
    logger.info("Logged in as %s (using %s)", client.user, chat.model)
    await find_webhook_channel()
    await sync_missed_messages()
    logger.info("Startup sync complete.")


@client.event
async def on_message(message: discord.Message) -> None:
    # Ignore the bot's own messages and anything that doesn't tag it
    if message.author == client.user or client.user not in message.mentions:
        return

    # 1. Clean the text (remove the @mention)
    prompt = strip_mention(message.content, client.user.id)
    if not prompt:
        await message.channel.send("You tagged me, but didn't say anything! What do you need?")
        return

    # 2. Store the message and update last_seen immediately so we don't double-process
    storage.add_message(make_entry(message, prompt))
    storage.update_last_seen()

    # 3. Show "typing..." in Discord while Claude thinks
    try:
        async with message.channel.typing():
            reply_text = await chat.ask(message.channel.id, message.author.display_name, prompt)
    except anthropic.AuthenticationError:
        logger.error("Claude error: invalid or missing ANTHROPIC_API_KEY")
        await message.channel.send("My Claude API key isn't set up correctly. Ask my owner to check it!")
        return
    except anthropic.RateLimitError:
        logger.warning("Claude error: rate limited")
        await message.channel.send("I'm getting too many requests right now. Try again in a moment!")
        return
    except anthropic.APIError as e:
        logger.error("Error calling Claude: %s", e)
        await message.channel.send("Sorry, my brain (Claude) is having trouble right now. Try again later!")
        return

    # 4. Send the reply back to Discord
    await send_reply(message, reply_text)


def run() -> None:
    if not config.DISCORD_BOT_TOKEN:
        raise SystemExit("Set DISCORD_BOT_TOKEN in your .env file first.")
    # Logging is configured in __main__, so don't let discord.py add a second handler
    client.run(config.DISCORD_BOT_TOKEN, log_handler=None)
