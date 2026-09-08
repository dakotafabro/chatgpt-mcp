from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup


@dataclass
class Message:
    role: str
    content: str
    model: str | None = None


@dataclass
class Conversation:
    title: str
    messages: list[Message] = field(default_factory=list)
    create_time: float | None = None
    url: str = ""


_SHARE_URL_RE = re.compile(
    r"https?://(?:chat\.openai\.com|chatgpt\.com)/share/(?:e/)?([a-f0-9\-]+)"
)


def _extract_share_id(url: str) -> str:
    m = _SHARE_URL_RE.match(url.strip())
    if not m:
        raise ValueError(
            f"Not a valid ChatGPT share URL: {url}\n"
            "Expected format: https://chatgpt.com/share/<id> or https://chatgpt.com/share/e/<id>"
        )
    return m.group(1)


def _resolve_react_router_data(raw: list[Any]) -> dict[str, Any]:
    cache: dict[int, Any] = {}

    def resolve_ref(idx: int) -> Any:
        if idx in cache:
            return cache[idx]
        cache[idx] = None
        result = resolve_val(raw[idx])
        cache[idx] = result
        return result

    def resolve_val(val: Any) -> Any:
        if isinstance(val, dict):
            has_refs = any(k.startswith("_") and k[1:].isdigit() for k in val)
            if has_refs:
                resolved = {}
                for k, v in val.items():
                    if k.startswith("_") and k[1:].isdigit():
                        key_idx = int(k[1:])
                        real_key = str(resolve_ref(key_idx))
                        if isinstance(v, int):
                            real_val = None if v < 0 else resolve_ref(v)
                        else:
                            real_val = resolve_val(v)
                        resolved[real_key] = real_val
                    else:
                        resolved[k] = resolve_val(v)
                return resolved
            return {k: resolve_val(v) for k, v in val.items()}
        if isinstance(val, list):
            return [resolve_ref(item) if isinstance(item, int) else resolve_val(item) for item in val]
        return val

    return resolve_ref(0)

def _parse_streamed_data(html: str) -> dict[str, Any] | None:
    pattern = re.compile(
        r'streamController\.enqueue\("((?:[^"\\]|\\.)*)"\)', re.DOTALL
    )
    matches = pattern.findall(html)

    for chunk_escaped in matches:
        try:
            chunk = chunk_escaped.encode().decode("unicode_escape")
        except Exception:
            continue

        chunk = chunk.strip()
        if not chunk.startswith("["):
            continue

        try:
            raw = json.loads(chunk)
        except json.JSONDecodeError:
            continue

        if not isinstance(raw, list) or len(raw) < 2:
            continue

        resolved = _resolve_react_router_data(raw)
        loader = resolved.get("loaderData", {})
        route_data = (
            loader.get("routes/share.$shareId.($action)", {})
            or loader.get("routes/share.e.$shareId.($action)", {})
        )

        if route_data.get("loginRequired"):
            return {"type": "error", "message": "This share link requires authentication (login required)."}

        if "serverResponse" in route_data:
            return route_data["serverResponse"]

    return None


def _parse_next_data(html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        data = json.loads(script.string)
        return data.get("props", {}).get("pageProps", {}).get("serverResponse", {}).get("data", {})
    except (json.JSONDecodeError, AttributeError):
        return None


def _extract_messages_from_mapping(data: dict[str, Any]) -> list[Message]:
    mapping = data.get("mapping", {})
    if not mapping:
        linear = data.get("linear_conversation", [])
        if linear:
            return _extract_messages_from_linear(linear)
        return []

    root_ids = [
        nid for nid, node in mapping.items()
        if node.get("parent") is None
    ]

    messages: list[Message] = []
    visited: set[str] = set()

    def walk(node_id: str) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = mapping.get(node_id, {})
        msg = node.get("message")
        if msg:
            role = msg.get("author", {}).get("role", "unknown")
            if role in ("user", "assistant"):
                parts = msg.get("content", {}).get("parts", [])
                text_parts = []
                for p in parts:
                    if isinstance(p, str):
                        text_parts.append(p)
                    elif isinstance(p, dict) and p.get("content_type") == "text":
                        text_parts.append(p.get("text", ""))
                content = "\n".join(text_parts).strip()
                if content:
                    model_slug = msg.get("metadata", {}).get("model_slug")
                    messages.append(Message(role=role, content=content, model=model_slug))

        for child_id in node.get("children", []):
            walk(child_id)

    for rid in root_ids:
        walk(rid)

    return messages


def _extract_messages_from_linear(linear: list[dict[str, Any]]) -> list[Message]:
    messages: list[Message] = []
    for entry in linear:
        msg = entry.get("message")
        if not msg:
            continue
        role = msg.get("author", {}).get("role", "unknown")
        if role not in ("user", "assistant"):
            continue
        parts = msg.get("content", {}).get("parts", [])
        text_parts = []
        for p in parts:
            if isinstance(p, str):
                text_parts.append(p)
            elif isinstance(p, dict) and p.get("content_type") == "text":
                text_parts.append(p.get("text", ""))
        content = "\n".join(text_parts).strip()
        if content:
            model_slug = msg.get("metadata", {}).get("model_slug")
            messages.append(Message(role=role, content=content, model=model_slug))
    return messages


async def fetch_conversation(url: str) -> Conversation:
    share_id = _extract_share_id(url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url.strip(), headers=headers)
        resp.raise_for_status()
        html = resp.text

    data = _parse_streamed_data(html)

    if not data:
        data = _parse_next_data(html)

    if not data:
        if "/share/e/" in url:
            raise ValueError(
                f"Could not extract conversation data from {url}. "
                "Links with /share/e/ require authentication. "
                "Use the public share link instead (Share > Copy link in ChatGPT)."
            )
        raise ValueError(
            f"Could not extract conversation data from {url}. "
            "The link may not be publicly shared, or OpenAI may have changed their page structure."
        )

    if isinstance(data, dict) and "type" in data and data["type"] == "error":
        raise ValueError(f"ChatGPT returned an error for share ID {share_id}. The conversation may not exist or is no longer shared.")

    if isinstance(data, dict) and "data" in data:
        conv_data = data["data"]
    else:
        conv_data = data if isinstance(data, dict) else {}

    title = conv_data.get("title", "Untitled Conversation")
    create_time = conv_data.get("create_time")
    messages = _extract_messages_from_mapping(conv_data)

    if not messages:
        raise ValueError(
            f"Parsed the page but found no messages. The conversation may be empty or the format changed."
        )

    return Conversation(
        title=title,
        messages=messages,
        create_time=create_time,
        url=url.strip(),
    )


def format_as_markdown(conv: Conversation) -> str:
    lines = [f"# {conv.title}", ""]

    if conv.url:
        lines.append(f"*Source: {conv.url}*")
        lines.append("")

    lines.append(f"*{len(conv.messages)} messages*")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in conv.messages:
        role_label = "**User**" if msg.role == "user" else "**Assistant**"
        if msg.model:
            role_label += f" ({msg.model})"
        lines.append(role_label)
        lines.append("")
        lines.append(msg.content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def format_as_json(conv: Conversation) -> str:
    return json.dumps(
        {
            "title": conv.title,
            "url": conv.url,
            "create_time": conv.create_time,
            "message_count": len(conv.messages),
            "messages": [
                {"role": m.role, "content": m.content, "model": m.model}
                for m in conv.messages
            ],
        },
        indent=2,
    )
