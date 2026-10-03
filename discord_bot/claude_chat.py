from anthropic import AsyncAnthropic

from . import config


class ClaudeChat:
    """Asks Claude questions and remembers recent conversation per channel."""

    def __init__(self, client=None, model=config.CLAUDE_MODEL, system_prompt=config.SYSTEM_PROMPT,
                 max_history=config.MAX_HISTORY, max_tokens=config.MAX_TOKENS):
        # AsyncAnthropic reads ANTHROPIC_API_KEY from the environment automatically
        self.client = client or AsyncAnthropic()
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.max_tokens = max_tokens
        # Per-channel conversation memory (in RAM, resets when the bot restarts)
        self.history = {}  # { channel_id: [{"role": ..., "content": ...}] }

    async def ask(self, channel_id, author_name, prompt):
        history = self.history.setdefault(channel_id, [])
        history.append({"role": "user", "content": f"{author_name}: {prompt}"})

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
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
        # max_history is even, so the trimmed history still starts with a user turn.
        self.history[channel_id] = history[-self.max_history:]
        return reply_text
