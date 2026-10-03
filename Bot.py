import asyncio
import discord
import json
import os
from datetime import datetime, timezone

import anthropic
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

import Connect  # Sends replies through the Discord webhook

# Load DISCORD_BOT_TOKEN and ANTHROPIC_API_KEY from the .env file
load_dotenv()

# --- Claude Setup ---
# AsyncAnthropic reads ANTHROPIC_API_KEY from the environment automatically
claude = AsyncAnthropic()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")  # Fast and cheap
SYSTEM_PROMPT = (
    "You are a helpful Discord bot. Keep your answers concise and friendly. "
    "Each user message starts with the sender's name, e.g. 'Alice: ...'."
)
MAX_HISTORY = 10  # Messages of context kept per channel
DISCORD_LIMIT = 2000  # Discord's per-message character limit

# Per-channel conversation memory (in RAM, resets when the bot restarts)
conversation_history = {}  # { channel_id: [{"role": ..., "content": ...}] }

# --- Discord Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)

# The webhook in Connect.py can only post in one channel, so look it up once
try:
    WEBHOOK_CHANNEL_ID = Connect.get_webhook_channel_id()
except Exception as e:
    print(f"Couldn't reach the Connect.py webhook ({e}); replying as the bot instead")
    WEBHOOK_CHANNEL_ID = None

# File to store the timestamp of the last message we processed
STATE_FILE = "bot_state.json"
MESSAGES_FILE = "messages.json"

def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return default

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def strip_mention(content):
    # Mentions can look like <@id> or <@!id> (nickname mention)
    return content.replace(f"<@{client.user.id}>", "").replace(f"<@!{client.user.id}>", "").strip()

def split_message(text, limit=DISCORD_LIMIT):
    # Split long replies into chunks, preferring to break on newlines
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks

async def ask_claude(channel_id, author_name, prompt):
    history = conversation_history.setdefault(channel_id, [])
    history.append({"role": "user", "content": f"{author_name}: {prompt}"})

    try:
        response = await claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history,
        )
    except Exception:
        history.pop()  # Don't keep a question that never got an answer
        raise

    reply_text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not reply_text:
        reply_text = "Hmm, I don't have an answer for that."

    history.append({"role": "assistant", "content": reply_text})
    # Keep only the most recent messages so we don't exceed token limits.
    # MAX_HISTORY is even, so the trimmed history still starts with a user turn.
    conversation_history[channel_id] = history[-MAX_HISTORY:]
    return reply_text

# Load existing stored messages
stored_messages = load_json(MESSAGES_FILE, [])

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (using {CLAUDE_MODEL})")

    # 1. Get the last time the bot was online
    state = load_json(STATE_FILE, {})
    last_seen_str = state.get("last_seen")

    if last_seen_str:
        last_seen = datetime.fromisoformat(last_seen_str)
        print(f"Fetching missed messages since {last_seen}...")
    else:
        last_seen = None
        print("First run! Fetching recent history...")

    # 2. Loop through all channels the bot can see
    for guild in client.guilds:
        for channel in guild.text_channels:
            # Check if bot has permission to read history
            if not channel.permissions_for(guild.me).read_message_history:
                continue

            try:
                # 3. Fetch messages sent after `last_seen` (or last 100 if first run)
                # Note: Discord API limits history fetching to 100 messages at a time by default
                async for message in channel.history(limit=100, after=last_seen):
                    if message.author == client.user:
                        continue

                    if client.user in message.mentions:
                        clean_text = strip_mention(message.content)

                        new_entry = {
                            "author": str(message.author),
                            "text": clean_text,
                            "channel": str(message.channel),
                            "time": message.created_at.isoformat()
                        }

                        stored_messages.append(new_entry)
                        print(f"Recovered missed message: {new_entry}")

            except discord.Forbidden:
                print(f"Missing permissions to read history in {channel.name}")
            except Exception as e:
                print(f"Error reading {channel.name}: {e}")

    # 4. Save the new messages and update the last_seen time
    save_json(MESSAGES_FILE, stored_messages)
    save_json(STATE_FILE, {"last_seen": datetime.now(timezone.utc).isoformat()})
    print("Startup sync complete.")

@client.event
async def on_message(message):
    # Ignore the bot's own messages
    if message.author == client.user:
        return

    if client.user not in message.mentions:
        return

    # 1. Clean the text (remove the @mention)
    prompt = strip_mention(message.content)

    if not prompt:
        await message.channel.send("You tagged me, but didn't say anything! What do you need?")
        return

    # 2. Store the message
    new_entry = {
        "author": str(message.author),
        "text": prompt,
        "channel": str(message.channel),
        "time": message.created_at.isoformat()
    }
    stored_messages.append(new_entry)
    save_json(MESSAGES_FILE, stored_messages)

    # Update the last_seen time immediately so we don't double-process
    save_json(STATE_FILE, {"last_seen": datetime.now(timezone.utc).isoformat()})

    # 3. Show "typing..." in Discord while Claude thinks
    try:
        async with message.channel.typing():
            reply_text = await ask_claude(message.channel.id, message.author.display_name, prompt)
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

    # 4. Send the reply, split to respect Discord's 2000-character limit
    if message.channel.id == WEBHOOK_CHANNEL_ID:
        # Reply through the Connect.py webhook, tagging who asked
        chunks = split_message(f"{message.author.mention} {reply_text}")
        for chunk in chunks:
            # requests is blocking, so run it off the event loop
            if not await asyncio.to_thread(Connect.send_message, chunk):
                await message.channel.send(chunk)  # Fall back to the bot if the webhook fails
        return

    chunks = split_message(reply_text)
    await message.reply(chunks[0], mention_author=False)
    for chunk in chunks[1:]:
        await message.channel.send(chunk)

# Read the token from an environment variable so it isn't hardcoded
client.run(os.environ["DISCORD_BOT_TOKEN"])
