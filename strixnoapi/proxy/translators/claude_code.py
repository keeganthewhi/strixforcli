"""Claude Code translator — Anthropic Messages API backed by Claude Max/Pro OAuth."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import HTTPException

from strixnoapi.proxy.translators.base import BaseTranslator


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from strixnoapi.proxy.credentials import OAuth
    from strixnoapi.proxy.settings import ProxySettings


log = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OAUTH_BETA = "oauth-2025-04-20"
CLAUDE_CODE_SYSTEM_PREFIX = "You are Claude Code, Anthropic's official CLI for Claude."
MAX_RETRY_429 = 2  # Anthropic throttles spam; retry sparingly
RETRY_BACKOFF_BASE_S = 8.0


class ClaudeCodeTranslator(BaseTranslator):
    name = "claude"
    upstream_url = ANTHROPIC_URL

    async def complete_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> dict[str, Any]:
        anthropic_body = self._to_anthropic(body)
        headers = self._headers(oauth, stream=False)
        resp = await self._post_with_retry(anthropic_body, headers, settings)
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

    async def _post_with_retry(
        self, body: dict[str, Any], headers: dict[str, str], settings: ProxySettings
    ) -> httpx.Response:
        """POST with silent retry on Anthropic 429/5xx (transient rate limits + server blips).

        Strix's warm_up_llm has no retry logic, so transient rate limits used
        to kill the whole scan. Absorbing a few retries here is invisible to
        upstream and dramatically reduces flake-out-on-warmup.

        Individual request timeout is capped at 45s regardless of
        `settings.inactivity_timeout_s` (which covers the whole retry loop) —
        a single upstream call must not hang for 30 minutes.
        """
        last_exc: Exception | None = None
        per_request_timeout = min(45.0, float(settings.inactivity_timeout_s))
        async with httpx.AsyncClient(timeout=per_request_timeout) as client:
            for attempt in range(MAX_RETRY_429 + 1):
                try:
                    resp = await client.post(ANTHROPIC_URL, json=body, headers=headers)
                except httpx.RequestError as e:
                    last_exc = e
                    log.warning("anthropic request error on attempt %d: %s", attempt + 1, e)
                    if attempt >= MAX_RETRY_429:
                        raise
                    await asyncio.sleep(RETRY_BACKOFF_BASE_S * (2**attempt))
                    continue
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt >= MAX_RETRY_429:
                        return resp
                    retry_after = resp.headers.get("retry-after")
                    wait_s = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else RETRY_BACKOFF_BASE_S * (2**attempt)
                    )
                    log.info(
                        "anthropic %s on attempt %d, retrying in %.1fs",
                        resp.status_code, attempt + 1, wait_s,
                    )
                    await asyncio.sleep(min(wait_s, 30.0))
                    continue
                return resp
        if last_exc:
            raise last_exc
        msg = "retry loop exited without response"
        raise RuntimeError(msg)

    async def stream_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> AsyncIterator[str]:
        anthropic_body = {**self._to_anthropic(body), "stream": True}
        headers = self._headers(oauth, stream=True)
        model = body.get("model") or anthropic_body["model"]
        chat_id = self.make_chat_id()

        try:
            async with httpx.AsyncClient(timeout=None) as client, client.stream(
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
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> dict[str, Any]:
        headers = self._headers(oauth, stream=False)
        async with httpx.AsyncClient(timeout=settings.inactivity_timeout_s) as client:
            resp = await client.post(ANTHROPIC_URL, json=body, headers=headers)
        self._raise_for_status(resp)
        return resp.json()

    async def stream_anthropic(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> AsyncIterator[str]:
        anthropic_body = {**body, "stream": True}
        headers = self._headers(oauth, stream=True)
        async with httpx.AsyncClient(timeout=None) as client, client.stream(
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

    def _headers(self, oauth: OAuth, stream: bool) -> dict[str, str]:
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
        """Translate OpenAI chat body to Anthropic Messages body.

        CRITICAL: the `anthropic-beta: oauth-2025-04-20` subscription path
        ONLY accepts the exact Claude Code system prompt; any appended or
        replaced text causes Anthropic to return a 429 "rate_limit_error".
        (Verified empirically 2026-04-17.)

        Workaround: lock `system` to the Claude Code prefix and fold the
        caller's real system content into the FIRST user message, wrapped
        with `<strix_system>...</strix_system>` so Claude still distinguishes
        task instructions from user content.
        """
        caller_system, msgs = self.extract_system_and_messages(body)
        coerced_msgs = [self._coerce_message(m) for m in msgs]
        if caller_system:
            self._prepend_to_first_user(coerced_msgs, caller_system)

        model = body.get("model") or "claude-sonnet-4-6"
        if model.startswith("openai/"):
            model = model.removeprefix("openai/")
        anthropic: dict[str, Any] = {
            "model": model,
            "messages": coerced_msgs,
            "system": CLAUDE_CODE_SYSTEM_PREFIX,
            "max_tokens": int(body.get("max_tokens") or 8192),
        }
        if "temperature" in body:
            anthropic["temperature"] = float(body["temperature"])
        if "top_p" in body:
            anthropic["top_p"] = float(body["top_p"])
        if "stop" in body and body["stop"] is not None:
            anthropic["stop_sequences"] = (
                body["stop"] if isinstance(body["stop"], list) else [body["stop"]]
            )
        tools = body.get("tools")
        if tools:
            anthropic["tools"] = self._translate_tools(tools)
        return anthropic

    @staticmethod
    def _prepend_to_first_user(
        coerced_msgs: list[dict[str, Any]], system_text: str
    ) -> None:
        """Mutates coerced_msgs: wraps system_text as <strix_system>...</strix_system>
        and prepends it to the first user message (creating one if none exist)."""
        wrapped = f"<strix_system>\n{system_text}\n</strix_system>\n\n"
        for m in coerced_msgs:
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, str):
                    m["content"] = wrapped + content
                elif isinstance(content, list):
                    text_items = [b for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    if text_items:
                        text_items[0]["text"] = wrapped + text_items[0].get("text", "")
                    else:
                        content.insert(0, {"type": "text", "text": wrapped})
                return
        coerced_msgs.insert(0, {"role": "user", "content": wrapped})

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

    def _translate_stream_event(  # noqa: PLR0911 — dispatch over event types
        self, event: dict[str, Any], model: str, chat_id: str
    ) -> str | None:
        """Map one Anthropic SSE event → one OpenAI chat-completion chunk.

        Anthropic streams a stable sequence:

          message_start -> (content_block_start -> content_block_delta* ->
          content_block_stop)+ -> message_delta -> message_stop

        LiteLLM / the OpenAI SDK expect a role delta on the first chunk,
        text deltas for the body, and a final chunk with finish_reason.
        Missing any of these → LiteLLM's stream-chunk-builder can fail
        to assemble a response and will time out the whole request.

        Previously we only emitted text_delta and dropped everything
        else, which was fine for short responses but could leave long
        tool-heavy turns with huge gaps between chunks → LiteLLM
        timeout.
        """
        t = event.get("type")
        if t == "message_start":
            # First chunk — carries role so OpenAI SDK knows a message is starting.
            return self.make_openai_chunk(
                {"role": "assistant", "content": ""},
                model=model,
                chat_id=chat_id,
            )
        if t == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "text":
                # Emit an empty delta to keep the stream lively.
                return self.make_openai_chunk({}, model=model, chat_id=chat_id)
            if block.get("type") == "tool_use":
                # Surface tool_use start as inline XML that strix's parser
                # can recognize even without native tool-calling.
                name = block.get("name", "")
                return self.make_openai_chunk(
                    {"content": f'\n<invoke name="{name}">'},
                    model=model,
                    chat_id=chat_id,
                )
            return None
        if t == "content_block_delta":
            delta = event.get("delta", {})
            dt = delta.get("type")
            if dt == "text_delta":
                return self.make_openai_chunk(
                    {"content": delta.get("text", "")},
                    model=model,
                    chat_id=chat_id,
                )
            if dt == "input_json_delta":
                partial = delta.get("partial_json", "")
                return self.make_openai_chunk(
                    {"content": partial},
                    model=model,
                    chat_id=chat_id,
                )
            if dt == "thinking_delta":
                # Surface extended-thinking content as regular text so the
                # scan log stays coherent; strix's parser ignores whitespace.
                return self.make_openai_chunk(
                    {"content": delta.get("thinking", "")},
                    model=model,
                    chat_id=chat_id,
                )
            return None
        if t == "content_block_stop":
            # Close any open tool_use XML so strix's XML parser terminates cleanly.
            return self.make_openai_chunk(
                {"content": "</invoke>\n"},
                model=model,
                chat_id=chat_id,
            )
        if t == "message_delta":
            # Anthropic signals stop_reason here; we emit nothing — the
            # outer stream loop emits the final finish_reason chunk.
            return None
        if t == "message_stop":
            return None
        if t == "error":
            err = event.get("error", {})
            return self.make_openai_chunk(
                {"content": f"\n[upstream error: {err.get('message', 'unknown')}]"},
                model=model,
                chat_id=chat_id,
            )
        # "ping" and any unknown events — ignore but don't starve the stream.
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
