"""Input validation for incoming proxy requests."""

from __future__ import annotations

from fastapi import HTTPException


ALLOWED_ROLES: frozenset[str] = frozenset({"system", "user", "assistant", "tool", "function"})
SUSPICIOUS_CONTROL_CHARS: frozenset[int] = frozenset(
    i for i in range(0x20) if i not in {0x09, 0x0A, 0x0D}
)


def validate_request_body(body: dict, max_prompt_bytes: int, max_message_bytes: int) -> None:
    if not isinstance(body, dict):
        raise HTTPException(400, "request body must be a JSON object")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, "messages must be a non-empty list")
    total = 0
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise HTTPException(400, f"messages[{i}] must be an object")
        role = msg.get("role")
        if role not in ALLOWED_ROLES:
            raise HTTPException(400, f"messages[{i}].role invalid: {role!r}")
        content = msg.get("content")
        size = _estimate_content_size(content)
        if size > max_message_bytes:
            raise HTTPException(413, f"messages[{i}] exceeds per-message limit")
        total += size
        if total > max_prompt_bytes:
            raise HTTPException(413, "total prompt size exceeds limit")
        _reject_control_chars(content, i)


def _estimate_content_size(content: object) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.encode("utf-8", errors="replace"))
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if isinstance(text, str):
                    total += len(text.encode("utf-8", errors="replace"))
        return total
    return 0


def _reject_control_chars(content: object, idx: int) -> None:
    if isinstance(content, str):
        for ch in content:
            if ord(ch) in SUSPICIOUS_CONTROL_CHARS:
                raise HTTPException(400, f"messages[{idx}] contains disallowed control chars")
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                _reject_control_chars(item.get("text"), idx)


def flatten_text(messages: list[dict]) -> str:
    out: list[str] = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            out.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        out.append(text)
    return "\n".join(out)
