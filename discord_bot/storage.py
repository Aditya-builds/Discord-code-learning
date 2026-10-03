import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import discord

MessageEntry = dict[str, str]
Conversation = list[dict[str, str]]  # [{"role": ..., "content": ...}]


def load_json(filepath: str | Path, default: Any) -> Any:
    filepath = Path(filepath)
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath: str | Path, data: Any) -> None:
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class BotStorage:
    """Stored @mentions, the last time the bot was online, and Claude's conversation memory."""

    def __init__(self, state_file: str | Path, messages_file: str | Path,
                 conversations_file: str | Path | None = None):
        self.state_file = Path(state_file)
        self.messages_file = Path(messages_file)
        self.conversations_file = Path(conversations_file) if conversations_file else None
        self.messages: list[MessageEntry] = load_json(self.messages_file, [])

    def add_message(self, message_entry: MessageEntry, save: bool = True) -> None:
        self.messages.append(message_entry)
        if save:
            self.save_messages()

    def save_messages(self) -> None:
        save_json(self.messages_file, self.messages)

    def get_last_seen(self) -> datetime | None:
        last_seen_str = load_json(self.state_file, {}).get("last_seen")
        return datetime.fromisoformat(last_seen_str) if last_seen_str else None

    def update_last_seen(self) -> None:
        save_json(self.state_file, {"last_seen": datetime.now(timezone.utc).isoformat()})

    def load_conversations(self) -> dict[int, Conversation]:
        if not self.conversations_file:
            return {}
        # JSON object keys are always strings, so turn channel IDs back into ints
        return {int(k): v for k, v in load_json(self.conversations_file, {}).items()}

    def save_conversations(self, conversations: dict[int, Conversation]) -> None:
        if self.conversations_file:
            save_json(self.conversations_file, {str(k): v for k, v in conversations.items()})


def make_entry(message: discord.Message, text: str) -> MessageEntry:
    """Build the record we store for a Discord message."""
    return {
        "author": str(message.author),
        "text": text,
        "channel": str(message.channel),
        "time": message.created_at.isoformat(),
    }
