"""Abstract base for OAuth-backed LLM translators."""

from __future__ import annotations

import abc
import json
import secrets
import time
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from strixnoapi.proxy.credentials import OAuth
    from strixnoapi.proxy.settings import ProxySettings


class TranslatorError(RuntimeError):
    pass


class BaseTranslator(abc.ABC):
    name: str
    upstream_url: str

    # --- OpenAI-compatible surface ------------------------------------------

    @abc.abstractmethod
    async def complete_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def stream_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> AsyncIterator[str]:
        raise NotImplementedError

    # --- Anthropic-compatible surface (optional — only Claude uses it) ------

    async def complete_anthropic(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> dict[str, Any]:
        raise TranslatorError(f"{self.name} does not implement Anthropic wire format")

    def stream_anthropic(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> AsyncIterator[str]:
        raise TranslatorError(f"{self.name} does not implement Anthropic streaming")

    # --- helpers ------------------------------------------------------------

    @staticmethod
    def make_chat_id() -> str:
        return f"chatcmpl-{secrets.token_hex(8)}"

    @staticmethod
    def make_openai_envelope(
        content: str, model: str, finish_reason: str = "stop", usage: dict | None = None
    ) -> dict[str, Any]:
        return {
            "id": BaseTranslator.make_chat_id(),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    @staticmethod
    def make_openai_chunk(
        delta: dict[str, Any], model: str, finish_reason: str | None = None, chat_id: str | None = None
    ) -> str:
        payload = {
            "id": chat_id or BaseTranslator.make_chat_id(),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"

    @staticmethod
    def sse_done() -> str:
        return "data: [DONE]\n\n"

    @staticmethod
    def extract_system_and_messages(body: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        rest: list[dict[str, Any]] = []
        for m in body.get("messages", []):
            role = m.get("role")
            if role == "system":
                content = m.get("content")
                if isinstance(content, str):
                    system_parts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            text = item.get("text")
                            if isinstance(text, str):
                                system_parts.append(text)
            else:
                rest.append(m)
        return "\n\n".join(system_parts), rest
