import asyncio

import anthropic
import discord

from . import config, webhook
from .claude_chat import ClaudeChat
from .storage import BotStorage, make_entry
from .text import split_message, strip_mention

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)
chat = ClaudeChat()
storage = BotStorage(config.STATE_FILE, config.MESSAGES_FILE)

# The webhook can only post in one channel; looked up once in on_ready
webhook_channel_id = None


async def find_webhook_channel():
    global webhook_channel_id
    if not config.DISCORD_WEBHOOK_URL:
        return
    try:
        # requests is blocking, so run it off the event loop
        webhook_channel_id = await asyncio.to_thread(webhook.get_webhook_channel_id)
    except Exception as e:
        print(f"Couldn't reach the webhook ({e}); replying as the bot instead")


async def sync_missed_messages():
    # 1. Get the last time the bot was online
    last_seen = storage.get_last_seen()
    if last_seen:
        print(f"Fetching missed messages since {last_seen}...")
    else:
        print("First run! Fetching recent history...")

    # 2. Loop through all channels the bot can see
    for guild in client.guilds:
        for channel in guild.text_channels:
            # Check if bot has permission to read history
            if not channel.permissions_for(guild.me).read_message_history:
                continue

            try:
                # 3. Fetch messages sent after `last_seen` (or the most recent ones on first run)
                async for message in channel.history(limit=config.HISTORY_FETCH_LIMIT, after=last_seen):
                    if message.author == client.user or client.user not in message.mentions:
                        continue

                    entry = make_entry(message, strip_mention(message.content, client.user.id))
                    storage.add_message(entry, save=False)
                    print(f"Recovered missed message: {entry}")

            except discord.Forbidden:
                print(f"Missing permissions to read history in {channel.name}")
            except Exception as e:
                print(f"Error reading {channel.name}: {e}")

    # 4. Save the new messages and update the last_seen time
    storage.save_messages()
    storage.update_last_seen()


async def send_reply(message, reply_text):
    # Split to respect Discord's 2000-character limit
    if message.channel.id == webhook_channel_id:
        # Reply through the webhook, tagging who asked
        for chunk in split_message(f"{message.author.mention} {reply_text}"):
            if not await asyncio.to_thread(webhook.send_message, chunk):
                await message.channel.send(chunk)  # Fall back to the bot if the webhook fails
        return

    chunks = split_message(reply_text)
    await message.reply(chunks[0], mention_author=False)
    for chunk in chunks[1:]:
        await message.channel.send(chunk)


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (using {chat.model})")
    await find_webhook_channel()
    await sync_missed_messages()
    print("Startup sync complete.")


@client.event
async def on_message(message):
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
        print("Claude error: invalid or missing ANTHROPIC_API_KEY")
        await message.channel.send("My Claude API key isn't set up correctly. Ask my owner to check it!")
        return
    except anthropic.RateLimitError:
        print("Claude error: rate limited")
        await message.channel.send("I'm getting too many requests right now. Try again in a moment!")
        return
    except anthropic.APIError as e:
        print(f"Error calling Claude: {e}")
        await message.channel.send("Sorry, my brain (Claude) is having trouble right now. Try again later!")
        return

    # 4. Send the reply back to Discord
    await send_reply(message, reply_text)


def run():
    if not config.DISCORD_BOT_TOKEN:
        raise SystemExit("Set DISCORD_BOT_TOKEN in your .env file first.")
    client.run(config.DISCORD_BOT_TOKEN)
