"""Claude Code translator — Anthropic Messages API backed by Claude Max/Pro OAuth."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import HTTPException

from strixnoapi.proxy.translators.base import BaseTranslator


if TYPE_CHECKING:
    from strixnoapi.proxy.credentials import OAuth
    from strixnoapi.proxy.settings import ProxySettings


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OAUTH_BETA = "oauth-2025-04-20"
CLAUDE_CODE_SYSTEM_PREFIX = "You are Claude Code, Anthropic's official CLI for Claude."


class ClaudeCodeTranslator(BaseTranslator):
    name = "claude"
    upstream_url = ANTHROPIC_URL

    async def complete_openai(
        self, body: dict[str, Any], oauth: "OAuth", settings: "ProxySettings"
    ) -> dict[str, Any]:
        anthropic_body = self._to_anthropic(body)
        headers = self._headers(oauth, stream=False)
        async with httpx.AsyncClient(timeout=settings.inactivity_timeout_s) as client:
            resp = await client.post(ANTHROPIC_URL, json=anthropic_body, headers=headers)
        self._raise_for_status(resp)
        data = resp.json()
        text = self._extract_text(data)
        usage = self._translate_usage(data.get("usage"))
        return self.make_openai_envelope(
            content=text,
            model=body.get("model") or anthropic_body["model"],
            finish_reason=self._map_stop_reason(data.get("stop_reason")),
            usage=usage,
        )

    async def stream_openai(
        self, body: dict[str, Any], oauth: "OAuth", settings: "ProxySettings"
    ) -> AsyncIterator[str]:
        anthropic_body = {**self._to_anthropic(body), "stream": True}
        headers = self._headers(oauth, stream=True)
        model = body.get("model") or anthropic_body["model"]
        chat_id = self.make_chat_id()

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", ANTHROPIC_URL, json=anthropic_body, headers=headers
                ) as resp:
                    if resp.status_code >= 400:
                        body_text = (await resp.aread()).decode("utf-8", errors="replace")
                        raise HTTPException(
                            status_code=resp.status_code,
                            detail=f"Anthropic error: {body_text[:500]}",
                        )
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line.removeprefix("data:").strip()
                        if not raw:
                            continue
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        chunk = self._translate_stream_event(event, model, chat_id)
                        if chunk:
                            yield chunk
        except httpx.RequestError as e:
            raise HTTPException(502, f"upstream request failed: {e}") from e

        yield self.make_openai_chunk(delta={}, model=model, finish_reason="stop", chat_id=chat_id)
        yield self.sse_done()

    async def complete_anthropic(
        self, body: dict[str, Any], oauth: "OAuth", settings: "ProxySettings"
    ) -> dict[str, Any]:
        headers = self._headers(oauth, stream=False)
        async with httpx.AsyncClient(timeout=settings.inactivity_timeout_s) as client:
            resp = await client.post(ANTHROPIC_URL, json=body, headers=headers)
        self._raise_for_status(resp)
        return resp.json()

    async def stream_anthropic(
        self, body: dict[str, Any], oauth: "OAuth", settings: "ProxySettings"
    ) -> AsyncIterator[str]:
        anthropic_body = {**body, "stream": True}
        headers = self._headers(oauth, stream=True)
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", ANTHROPIC_URL, json=anthropic_body, headers=headers
            ) as resp:
                if resp.status_code >= 400:
                    body_text = (await resp.aread()).decode("utf-8", errors="replace")
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Anthropic error: {body_text[:500]}",
                    )
                async for line in resp.aiter_lines():
                    if line:
                        yield f"{line}\n"

    # ---- helpers ---------------------------------------------------------

    def _headers(self, oauth: "OAuth", stream: bool) -> dict[str, str]:
        h = {
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-beta": OAUTH_BETA,
            "authorization": f"Bearer {oauth.access_token}",
            "user-agent": "strixnoapi/0.1.0",
        }
        if stream:
            h["accept"] = "text/event-stream"
        return h

    def _to_anthropic(self, body: dict[str, Any]) -> dict[str, Any]:
        system, msgs = self.extract_system_and_messages(body)
        system = f"{CLAUDE_CODE_SYSTEM_PREFIX}\n\n{system}" if system else CLAUDE_CODE_SYSTEM_PREFIX
        model = body.get("model") or "claude-sonnet-4-6"
        if model.startswith("openai/"):
            model = model.removeprefix("openai/")
        anthropic: dict[str, Any] = {
            "model": model,
            "messages": [self._coerce_message(m) for m in msgs],
            "system": system,
            "max_tokens": int(body.get("max_tokens") or 8192),
        }
        if "temperature" in body:
            anthropic["temperature"] = float(body["temperature"])
        if "top_p" in body:
            anthropic["top_p"] = float(body["top_p"])
        if "stop" in body and body["stop"] is not None:
            anthropic["stop_sequences"] = body["stop"] if isinstance(body["stop"], list) else [body["stop"]]
        tools = body.get("tools")
        if tools:
            anthropic["tools"] = self._translate_tools(tools)
        return anthropic

    @staticmethod
    def _coerce_message(m: dict[str, Any]) -> dict[str, Any]:
        role = m.get("role", "user")
        if role == "tool":
            role = "user"
        content = m.get("content")
        if isinstance(content, str):
            return {"role": role, "content": content}
        if isinstance(content, list):
            blocks: list[dict[str, Any]] = []
            for item in content:
                if isinstance(item, dict):
                    t = item.get("type")
                    if t == "text":
                        blocks.append({"type": "text", "text": item.get("text", "")})
                    elif t == "image_url":
                        url = item.get("image_url", {}).get("url", "") if isinstance(item.get("image_url"), dict) else ""
                        blocks.append({
                            "type": "image",
                            "source": {"type": "url", "url": url},
                        })
            return {"role": role, "content": blocks or [{"type": "text", "text": ""}]}
        return {"role": role, "content": ""}

    @staticmethod
    def _translate_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            fn = t.get("function") if isinstance(t.get("function"), dict) else t
            name = fn.get("name")
            if not name:
                continue
            out.append({
                "name": name,
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters") or {"type": "object"},
            })
        return out

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        parts: list[str] = []
        for block in data.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)

    @staticmethod
    def _translate_usage(u: dict[str, Any] | None) -> dict[str, Any]:
        if not u:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        input_t = int(u.get("input_tokens") or 0)
        output_t = int(u.get("output_tokens") or 0)
        cached = int(u.get("cache_read_input_tokens") or 0)
        return {
            "prompt_tokens": input_t,
            "completion_tokens": output_t,
            "total_tokens": input_t + output_t,
            "prompt_tokens_details": {"cached_tokens": cached},
        }

    @staticmethod
    def _map_stop_reason(reason: str | None) -> str:
        if reason == "end_turn":
            return "stop"
        if reason == "max_tokens":
            return "length"
        if reason == "stop_sequence":
            return "stop"
        if reason == "tool_use":
            return "tool_calls"
        return "stop"

    def _translate_stream_event(
        self, event: dict[str, Any], model: str, chat_id: str
    ) -> str | None:
        t = event.get("type")
        if t == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                return self.make_openai_chunk(
                    {"role": "assistant", "content": delta.get("text", "")},
                    model=model,
                    chat_id=chat_id,
                )
        return None

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise HTTPException(
                401,
                "Claude OAuth token rejected (401). Run `claude` to refresh credentials.",
            )
        if resp.status_code == 429:
            raise HTTPException(
                429,
                "Claude subscription rate limit reached. Wait and retry.",
                headers={"Retry-After": "60"},
            )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except json.JSONDecodeError:
                detail = resp.text[:500]
            raise HTTPException(resp.status_code, f"Anthropic upstream error: {detail}")
