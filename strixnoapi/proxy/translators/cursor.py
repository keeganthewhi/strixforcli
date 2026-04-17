"""Cursor translator — Cursor's proxy API via session token.

Status: experimental. Cursor's public CLI (`cursor-agent`) targets an
internal API endpoint; this translator implements the pattern current as
of 2026-Q1. If the endpoint shape changes, the fallback is to delegate
to `cursor-agent -p` as a subprocess (see `cursor_subprocess.py` — future).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import HTTPException

from strixnoapi.proxy.translators.base import BaseTranslator


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from strixnoapi.proxy.credentials import OAuth
    from strixnoapi.proxy.settings import ProxySettings


CURSOR_API_URL = "https://api.cursor.com/v1/chat/completions"


class CursorTranslator(BaseTranslator):
    name = "cursor"
    upstream_url = CURSOR_API_URL

    async def complete_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> dict[str, Any]:
        request_body = self._to_cursor(body)
        headers = self._headers(oauth)
        async with httpx.AsyncClient(timeout=settings.inactivity_timeout_s) as client:
            resp = await client.post(CURSOR_API_URL, json=request_body, headers=headers)
        self._raise_for_status(resp)
        data = resp.json()
        if "choices" in data:
            return data
        text = self._extract_text(data)
        return self.make_openai_envelope(
            content=text, model=body.get("model") or "cursor-default"
        )

    async def stream_openai(
        self, body: dict[str, Any], oauth: OAuth, settings: ProxySettings
    ) -> AsyncIterator[str]:
        request_body = {**self._to_cursor(body), "stream": True}
        headers = self._headers(oauth)
        model = body.get("model") or "cursor-default"
        chat_id = self.make_chat_id()
        try:
            async with httpx.AsyncClient(timeout=None) as client, client.stream(
                "POST", CURSOR_API_URL, json=request_body, headers=headers
            ) as resp:
                if resp.status_code >= 400:
                    body_text = (await resp.aread()).decode("utf-8", errors="replace")
                    self._raise_for_status_raw(resp.status_code, body_text)
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line.removeprefix("data:").strip()
                    if raw in ("", "[DONE]"):
                        if raw == "[DONE]":
                            break
                        continue
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    content = (
                        evt.get("choices", [{}])[0].get("delta", {}).get("content")
                        if evt.get("choices")
                        else self._extract_text(evt)
                    )
                    if content:
                        yield self.make_openai_chunk(
                            {"role": "assistant", "content": content},
                            model=model,
                            chat_id=chat_id,
                        )
        except httpx.RequestError as e:
            raise HTTPException(502, f"upstream request failed: {e}") from e
        yield self.make_openai_chunk({}, model=model, finish_reason="stop", chat_id=chat_id)
        yield self.sse_done()

    # ---- helpers ---------------------------------------------------------

    def _to_cursor(self, body: dict[str, Any]) -> dict[str, Any]:
        # Cursor's API is OpenAI-shaped; mostly pass-through.
        out = dict(body)
        out.pop("stream", None)
        return out

    @staticmethod
    def _headers(oauth: OAuth) -> dict[str, str]:
        return {
            "authorization": f"Bearer {oauth.access_token}",
            "content-type": "application/json",
            "user-agent": "strixnoapi/0.1.0 (cursor-bridge)",
        }

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        if "text" in data and isinstance(data["text"], str):
            return data["text"]
        if "message" in data and isinstance(data["message"], dict):
            content = data["message"].get("content")
            if isinstance(content, str):
                return content
        return ""

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise HTTPException(401, "Cursor session expired. Run `cursor-agent login`.")
        if resp.status_code == 429:
            raise HTTPException(
                429, "Cursor subscription rate limit reached.", headers={"Retry-After": "60"}
            )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except json.JSONDecodeError:
                detail = resp.text[:500]
            raise HTTPException(resp.status_code, f"Cursor upstream error: {detail}")

    @staticmethod
    def _raise_for_status_raw(status: int, body: str) -> None:
        if status == 401:
            raise HTTPException(401, "Cursor session expired. Run `cursor-agent login`.")
        if status == 429:
            raise HTTPException(429, "Cursor subscription rate limit reached.")
        raise HTTPException(status, f"Cursor upstream error: {body[:500]}")
