import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from discord_bot.claude_chat import ClaudeChat
from discord_bot.storage import BotStorage


class FakeMessages:
    """Stands in for claude.messages so tests never call the real API."""

    def __init__(self, reply="Paris", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


def make_chat(**kwargs):
    fake = FakeMessages(**kwargs)
    return ClaudeChat(client=SimpleNamespace(messages=fake), max_history=4), fake


class ClaudeChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_is_returned_and_remembered(self):
        chat, fake = make_chat()
        self.assertEqual(await chat.ask(1, "Alice", "capital of France?"), "Paris")
        await chat.ask(1, "Alice", "population?")
        # The follow-up was sent with the earlier exchange as context
        self.assertEqual(
            [m["content"] for m in fake.calls[1]["messages"]],
            ["Alice: capital of France?", "Paris", "Alice: population?"],
        )

    async def test_history_is_per_channel(self):
        chat, fake = make_chat()
        await chat.ask(1, "Alice", "hi")
        await chat.ask(2, "Bob", "hey")
        self.assertEqual(len(fake.calls[1]["messages"]), 1)

    async def test_history_is_trimmed_and_starts_with_user(self):
        chat, _ = make_chat()
        for i in range(5):
            await chat.ask(1, "Alice", f"q{i}")
        history = chat.history[1]
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["role"], "user")

    async def test_failed_call_does_not_keep_question(self):
        chat, _ = make_chat(error=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            await chat.ask(1, "Alice", "hi")
        self.assertEqual(chat.history[1], [])

    async def test_memory_survives_restart_when_storage_is_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = BotStorage(Path(tmp) / "s.json", Path(tmp) / "m.json", Path(tmp) / "c.json")
            fake = FakeMessages()
            chat = ClaudeChat(client=SimpleNamespace(messages=fake), storage=storage)
            await chat.ask(1, "Alice", "capital of France?")

            # A new ClaudeChat (like after a bot restart) picks up where the old one left off
            restarted = ClaudeChat(client=SimpleNamespace(messages=fake), storage=storage)
            await restarted.ask(1, "Alice", "population?")
            self.assertEqual(len(fake.calls[1]["messages"]), 3)

    async def test_empty_reply_gets_fallback_text(self):
        chat, _ = make_chat(reply="   ")
        self.assertEqual(await chat.ask(1, "Alice", "hi"), "Hmm, I don't have an answer for that.")


if __name__ == "__main__":
    unittest.main()
