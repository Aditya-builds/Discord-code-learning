# Discord Claude Bot

A Discord bot that stores every message it's tagged in and answers with Claude.

- Replies when @mentioned, showing "typing..." while Claude thinks
- Remembers the last 10 messages per channel, so follow-up questions work
- Catches up on mentions it missed while offline
- Splits long replies to fit Discord's 2000-character limit
- Optionally replies through a Discord webhook in the webhook's channel

## Project layout

```
discord_bot/
  __main__.py     Entry point (python -m discord_bot)
  bot.py          Discord client and event handlers
  claude_chat.py  Claude calls and per-channel conversation memory
  config.py       Settings, loaded from .env
  storage.py      Stored messages and last-seen timestamp (JSON files)
  text.py         Mention stripping and message splitting
  webhook.py      Send messages through a Discord webhook
tests/            Unit tests (no network or API calls)
data/             Runtime JSON files (not committed)
```

## Setup

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env   # then fill in your tokens
```

## Run

```powershell
.\venv\Scripts\python.exe -m discord_bot
```

Then type `@yourbot what is the capital of France?` in Discord.

Send a one-off message through the webhook:

```powershell
.\venv\Scripts\python.exe -m discord_bot.webhook "Hello from my code!"
```

## Test

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Configuration

| Variable | Required | Default |
|---|---|---|
| `DISCORD_BOT_TOKEN` | yes | |
| `ANTHROPIC_API_KEY` | yes | |
| `DISCORD_WEBHOOK_URL` | no | webhook replies disabled |
| `CLAUDE_MODEL` | no | `claude-haiku-4-5` |
| `BOT_DATA_DIR` | no | `data` |

Never commit `.env` — anyone with your Discord token can hijack the bot, and anyone
with your Anthropic key can run up your bill.
