from .config import DISCORD_LIMIT


def strip_mention(content: str, user_id: int) -> str:
    # Mentions can look like <@id> or <@!id> (nickname mention)
    return content.replace(f"<@{user_id}>", "").replace(f"<@!{user_id}>", "").strip()


def split_message(text: str, limit: int = DISCORD_LIMIT) -> list[str]:
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
