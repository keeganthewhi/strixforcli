"""Codex translator — ChatGPT backend-api via Codex session token.

Note: ChatGPT's subscription backend is not a documented public API. This
translator uses the endpoints Codex CLI itself uses, which may change. It
is pinned to the pattern current as of the upstream codex 0.12x line.
If the upstream endpoint changes, the `strix doctor` command is the first
thing to fail — users will see a clear error with a version hint.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import HTTPException

from strixnoapi.proxy.translators.base import BaseTranslator


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from strixnoapi.proxy.credentials import OAuth
    from strixnoapi.proxy.settings import ProxySettings


log = logging.getLogger(__name__)

CODEX_CHAT_URL = "https://chatgpt.com/backend-api/conversation"
CODEX_MODEL_DEFAULT = "gpt-5.4"


class CodexTranslator(BaseTranslator):
    name = "codex"
    upstream_url = CODEX_CHAT_URL

    async def complete_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> dict[str, Any]:
        collected: list[str] = []
        async for chunk in self._stream_raw(body, oauth, settings):
            if chunk:
                collected.append(chunk)
        text = "".join(collected)
        model = body.get("model") or CODEX_MODEL_DEFAULT
        return self.make_openai_envelope(content=text, model=model)

    async def stream_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> AsyncIterator[str]:
        model = body.get("model") or CODEX_MODEL_DEFAULT
        chat_id = self.make_chat_id()
        try:
            async for text in self._stream_raw(body, oauth, settings):
                if text:
                    yield self.make_openai_chunk(
                        {"role": "assistant", "content": text},
                        model=model,
                        chat_id=chat_id,
                    )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Codex upstream failure: {e}") from e
        yield self.make_openai_chunk({}, model=model, finish_reason="stop", chat_id=chat_id)
        yield self.sse_done()

    async def _stream_raw(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> AsyncIterator[str]:
        system, msgs = self.extract_system_and_messages(body)
        payload = self._make_codex_payload(
            system=system, messages=msgs, model=body.get("model") or CODEX_MODEL_DEFAULT
        )
        headers = self._headers(oauth)

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", CODEX_CHAT_URL, json=payload, headers=headers
            ) as resp:
                if resp.status_code >= 400:
                    body_text = (await resp.aread()).decode("utf-8", errors="replace")
                    self._raise_for_status(resp.status_code, body_text)

                last_text = ""
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line.removeprefix("data:").strip()
                    if raw == "[DONE]":
                        break
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    msg = evt.get("message") or {}
                    role = msg.get("author", {}).get("role") if isinstance(msg.get("author"), dict) else None
                    if role != "assistant":
                        continue
                    content = msg.get("content") or {}
                    parts = content.get("parts") if isinstance(content, dict) else None
                    if not parts:
                        continue
                    full = "".join(p for p in parts if isinstance(p, str))
                    delta = full[len(last_text):] if full.startswith(last_text) else full
                    if delta:
                        yield delta
                    last_text = full

    def _make_codex_payload(
        self, system: str, messages: list[dict[str, Any]], model: str
    ) -> dict[str, Any]:
        codex_msgs = []
        if system:
            codex_msgs.append({
                "id": secrets.token_hex(8),
                "author": {"role": "system"},
                "content": {"content_type": "text", "parts": [system]},
            })
        for m in messages:
            content = m.get("content")
            text = content if isinstance(content, str) else self._flatten(content)
            codex_msgs.append({
                "id": secrets.token_hex(8),
                "author": {"role": m.get("role", "user")},
                "content": {"content_type": "text", "parts": [text]},
            })
        return {
            "action": "next",
            "messages": codex_msgs,
            "model": model.removeprefix("openai/"),
            "stream": True,
            "parent_message_id": secrets.token_hex(8),
            "conversation_mode": {"kind": "primary_assistant"},
            "timezone_offset_min": 0,
            "history_and_training_disabled": True,
        }

    @staticmethod
    def _flatten(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    t = item.get("text") or item.get("content") or ""
                    if isinstance(t, str):
                        parts.append(t)
            return "\n".join(parts)
        return ""

    @staticmethod
    def _headers(oauth: OAuth) -> dict[str, str]:
        return {
            "authorization": f"Bearer {oauth.access_token}",
            "content-type": "application/json",
            "accept": "text/event-stream",
            "origin": "https://chatgpt.com",
            "referer": "https://chatgpt.com/",
            "user-agent": "strixnoapi/0.1.0 (codex-bridge)",
            "oai-device-id": oauth.extra.get("device_id") if oauth.extra else "strixnoapi",
        }

    @staticmethod
    def _raise_for_status(status: int, body: str) -> None:
        if status == 401:
            raise HTTPException(
                401,
                "Codex session rejected (401). Run `codex login` to refresh.",
            )
        if status == 429:
            raise HTTPException(
                429,
                "ChatGPT subscription rate limit reached.",
                headers={"Retry-After": "60"},
            )
        raise HTTPException(status, f"Codex upstream error: {body[:500]}")
