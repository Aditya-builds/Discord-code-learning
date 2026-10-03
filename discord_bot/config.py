import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY and DISCORD_WEBHOOK_URL from the .env file
load_dotenv(PROJECT_ROOT / ".env")

# --- Secrets (never hardcode these) ---
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")  # Optional

# --- Claude ---
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")  # Fast and cheap
MAX_TOKENS = 1024
SYSTEM_PROMPT = (
    "You are a helpful Discord bot. Keep your answers concise and friendly. "
    "Each user message starts with the sender's name, e.g. 'Alice: ...'."
)
MAX_HISTORY = 10  # Messages of context kept per channel (keep it even)

# --- Discord ---
DISCORD_LIMIT = 2000  # Discord's per-message character limit
HISTORY_FETCH_LIMIT = None  # Messages fetched per channel when catching up (None = all since last seen)
WEBHOOK_TIMEOUT = 10  # Seconds

# --- Storage ---
DATA_DIR = Path(os.environ.get("BOT_DATA_DIR", PROJECT_ROOT / "data"))
STATE_FILE = DATA_DIR / "bot_state.json"  # Timestamp of the last message we processed
MESSAGES_FILE = DATA_DIR / "messages.json"  # Every message the bot was tagged in
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"  # Claude memory per channel
