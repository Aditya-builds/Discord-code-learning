import tempfile
import unittest
from pathlib import Path

from discord_bot.storage import BotStorage


class BotStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        data_dir = Path(self.tmp.name) / "data"  # Doesn't exist yet: storage should create it
        self.state_file = data_dir / "bot_state.json"
        self.messages_file = data_dir / "messages.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_run_has_no_last_seen(self):
        self.assertIsNone(BotStorage(self.state_file, self.messages_file).get_last_seen())

    def test_last_seen_round_trip(self):
        storage = BotStorage(self.state_file, self.messages_file)
        storage.update_last_seen()
        self.assertIsNotNone(storage.get_last_seen().tzinfo)

    def test_messages_persist_across_instances(self):
        BotStorage(self.state_file, self.messages_file).add_message({"text": "hi"})
        self.assertEqual(BotStorage(self.state_file, self.messages_file).messages, [{"text": "hi"}])

    def test_conversations_round_trip_with_int_channel_ids(self):
        conversations_file = self.state_file.parent / "conversations.json"
        conversations = {123: [{"role": "user", "content": "Alice: hi"}]}
        BotStorage(self.state_file, self.messages_file, conversations_file).save_conversations(conversations)
        loaded = BotStorage(self.state_file, self.messages_file, conversations_file).load_conversations()
        self.assertEqual(loaded, conversations)

    def test_conversations_disabled_without_file(self):
        storage = BotStorage(self.state_file, self.messages_file)
        storage.save_conversations({1: []})
        self.assertEqual(storage.load_conversations(), {})


if __name__ == "__main__":
    unittest.main()
