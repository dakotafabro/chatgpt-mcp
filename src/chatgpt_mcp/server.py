from fastmcp import FastMCP

from chatgpt_mcp.parser import (
    fetch_conversation,
    format_as_json,
    format_as_markdown,
)

INSTRUCTIONS = """Read shared ChatGPT conversations.

Paste a ChatGPT share URL (https://chatgpt.com/share/...) and get the full
conversation transcript. Use fetch_chatgpt_conversation to get the markdown
transcript, or fetch_chatgpt_conversation_json for structured data.

Only works with publicly shared links (the ones you get from ChatGPT's
"Share" button). Private/unshared conversations cannot be accessed.
"""

mcp = FastMCP(
    "ChatGPT Reader",
    instructions=INSTRUCTIONS,
)


@mcp.tool()
async def fetch_chatgpt_conversation(url: str) -> str:
    """Fetch a shared ChatGPT conversation and return it as a markdown transcript.

    Args:
        url: A ChatGPT share URL (e.g. https://chatgpt.com/share/abc123 or
             https://chatgpt.com/share/e/abc123)

    Returns:
        The full conversation formatted as markdown with role labels and message content.
    """
    conv = await fetch_conversation(url)
    return format_as_markdown(conv)


@mcp.tool()
async def fetch_chatgpt_conversation_json(url: str) -> str:
    """Fetch a shared ChatGPT conversation and return it as structured JSON.

    Args:
        url: A ChatGPT share URL (e.g. https://chatgpt.com/share/abc123 or
             https://chatgpt.com/share/e/abc123)

    Returns:
        JSON with title, url, create_time, message_count, and messages array.
        Each message has role, content, and model fields.
    """
    conv = await fetch_conversation(url)
    return format_as_json(conv)


def main() -> None:
    mcp.run()
