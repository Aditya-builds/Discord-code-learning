from anthropic import AsyncAnthropic

from . import config
from .storage import BotStorage, Conversation


class ClaudeChat:
    """Asks Claude questions and remembers recent conversation per channel."""

    def __init__(self, client: AsyncAnthropic | None = None, storage: BotStorage | None = None,
                 model: str = config.CLAUDE_MODEL, system_prompt: str = config.SYSTEM_PROMPT,
                 max_history: int = config.MAX_HISTORY, max_tokens: int = config.MAX_TOKENS):
        # AsyncAnthropic reads ANTHROPIC_API_KEY from the environment automatically
        self.client = client or AsyncAnthropic()
        self.storage = storage  # Optional: saves memory to disk so it survives restarts
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.max_tokens = max_tokens
        self.history: dict[int, Conversation] = storage.load_conversations() if storage else {}

    async def ask(self, channel_id: int, author_name: str, prompt: str) -> str:
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
        if self.storage:
            self.storage.save_conversations(self.history)
        return reply_text
