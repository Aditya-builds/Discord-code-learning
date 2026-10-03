import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(filepath, default):
    filepath = Path(filepath)
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class BotStorage:
    """Stored @mentions plus the last time the bot was online."""

    def __init__(self, state_file, messages_file):
        self.state_file = Path(state_file)
        self.messages_file = Path(messages_file)
        self.messages = load_json(self.messages_file, [])

    def add_message(self, message_entry, save=True):
        self.messages.append(message_entry)
        if save:
            self.save_messages()

    def save_messages(self):
        save_json(self.messages_file, self.messages)

    def get_last_seen(self):
        last_seen_str = load_json(self.state_file, {}).get("last_seen")
        return datetime.fromisoformat(last_seen_str) if last_seen_str else None

    def update_last_seen(self):
        save_json(self.state_file, {"last_seen": datetime.now(timezone.utc).isoformat()})


def make_entry(message, text):
    """Build the record we store for a Discord message."""
    return {
        "author": str(message.author),
        "text": text,
        "channel": str(message.channel),
        "time": message.created_at.isoformat(),
    }
