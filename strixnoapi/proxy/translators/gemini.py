"""Gemini translator — Google generativelanguage API via OAuth."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import HTTPException

from strixnoapi.proxy.translators.base import BaseTranslator


if TYPE_CHECKING:
    from strixnoapi.proxy.credentials import OAuth
    from strixnoapi.proxy.settings import ProxySettings


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_DEFAULT_MODEL = "gemini-2.5-pro"


class GeminiTranslator(BaseTranslator):
    name = "gemini"
    upstream_url = GEMINI_API_BASE

    async def complete_openai(
        self, body: dict[str, Any], oauth: "OAuth", settings: "ProxySettings"
    ) -> dict[str, Any]:
        gemini_body, model = self._to_gemini(body)
        url = f"{GEMINI_API_BASE}/{model}:generateContent"
        headers = self._headers(oauth)
        async with httpx.AsyncClient(timeout=settings.inactivity_timeout_s) as client:
            resp = await client.post(url, json=gemini_body, headers=headers)
        self._raise_for_status(resp)
        data = resp.json()
        text = self._extract_text(data)
        usage = self._translate_usage(data.get("usageMetadata"))
        return self.make_openai_envelope(content=text, model=model, usage=usage)

    async def stream_openai(
        self, body: dict[str, Any], oauth: "OAuth", settings: "ProxySettings"
    ) -> AsyncIterator[str]:
        gemini_body, model = self._to_gemini(body)
        url = f"{GEMINI_API_BASE}/{model}:streamGenerateContent?alt=sse"
        headers = self._headers(oauth)
        chat_id = self.make_chat_id()
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=gemini_body, headers=headers) as resp:
                    if resp.status_code >= 400:
                        body_text = (await resp.aread()).decode("utf-8", errors="replace")
                        raise HTTPException(resp.status_code, f"Gemini error: {body_text[:500]}")
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line.removeprefix("data:").strip()
                        if not raw:
                            continue
                        try:
                            evt = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        text = self._extract_text(evt)
                        if text:
                            yield self.make_openai_chunk(
                                {"role": "assistant", "content": text},
                                model=model,
                                chat_id=chat_id,
                            )
        except httpx.RequestError as e:
            raise HTTPException(502, f"upstream request failed: {e}") from e

        yield self.make_openai_chunk({}, model=model, finish_reason="stop", chat_id=chat_id)
        yield self.sse_done()

    # ---- helpers ---------------------------------------------------------

    def _to_gemini(self, body: dict[str, Any]) -> tuple[dict[str, Any], str]:
        system, msgs = self.extract_system_and_messages(body)
        contents = []
        for m in msgs:
            role = m.get("role")
            gm_role = "user" if role in ("user", "tool") else "model"
            content = m.get("content")
            text = content if isinstance(content, str) else self._flatten(content)
            contents.append({"role": gm_role, "parts": [{"text": text}]})
        model = body.get("model") or GEMINI_DEFAULT_MODEL
        if model.startswith("openai/"):
            model = GEMINI_DEFAULT_MODEL
        out: dict[str, Any] = {"contents": contents}
        if system:
            out["systemInstruction"] = {"parts": [{"text": system}]}
        gen_cfg: dict[str, Any] = {}
        if "temperature" in body:
            gen_cfg["temperature"] = float(body["temperature"])
        if "max_tokens" in body:
            gen_cfg["maxOutputTokens"] = int(body["max_tokens"])
        if "top_p" in body:
            gen_cfg["topP"] = float(body["top_p"])
        if gen_cfg:
            out["generationConfig"] = gen_cfg
        return out, model

    @staticmethod
    def _flatten(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    t = item.get("text") or item.get("content") or ""
                    if isinstance(t, str):
                        parts.append(t)
            return "\n".join(parts)
        return ""

    @staticmethod
    def _headers(oauth: "OAuth") -> dict[str, str]:
        return {
            "authorization": f"Bearer {oauth.access_token}",
            "content-type": "application/json",
            "user-agent": "strixnoapi/0.1.0",
        }

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        parts_out: list[str] = []
        for c in candidates:
            content = c.get("content") if isinstance(c, dict) else None
            if not isinstance(content, dict):
                continue
            for p in content.get("parts") or []:
                if isinstance(p, dict):
                    t = p.get("text")
                    if isinstance(t, str):
                        parts_out.append(t)
        return "".join(parts_out)

    @staticmethod
    def _translate_usage(u: dict[str, Any] | None) -> dict[str, Any]:
        if not u:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        p = int(u.get("promptTokenCount") or 0)
        c = int(u.get("candidatesTokenCount") or 0)
        return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise HTTPException(401, "Gemini OAuth token expired. Run `gemini` to refresh.")
        if resp.status_code == 429:
            raise HTTPException(
                429,
                "Gemini subscription rate limit reached.",
                headers={"Retry-After": "60"},
            )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except json.JSONDecodeError:
                detail = resp.text[:500]
            raise HTTPException(resp.status_code, f"Gemini upstream error: {detail}")
