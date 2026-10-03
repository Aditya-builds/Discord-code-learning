import unittest

from discord_bot.text import split_message, strip_mention


class StripMentionTests(unittest.TestCase):
    def test_removes_plain_and_nickname_mentions(self):
        self.assertEqual(strip_mention("<@42> hello", 42), "hello")
        self.assertEqual(strip_mention("hi <@!42> there", 42), "hi  there")

    def test_keeps_other_users_mentions(self):
        self.assertEqual(strip_mention("<@42> ask <@7>", 42), "ask <@7>")


class SplitMessageTests(unittest.TestCase):
    def test_short_text_is_one_chunk(self):
        self.assertEqual(split_message("hello"), ["hello"])

    def test_empty_text_has_no_chunks(self):
        self.assertEqual(split_message(""), [])

    def test_long_text_respects_limit_and_prefers_newlines(self):
        chunks = split_message("\n".join(["line"] * 900))
        self.assertTrue(all(len(c) <= 2000 for c in chunks))
        self.assertTrue(all(c.endswith("line") for c in chunks))

    def test_text_without_newlines_is_hard_split(self):
        self.assertEqual(split_message("a" * 25, limit=10), ["a" * 10, "a" * 10, "a" * 5])


if __name__ == "__main__":
    unittest.main()
