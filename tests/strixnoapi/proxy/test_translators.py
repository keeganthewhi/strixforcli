"""Translator unit tests — upstream HTTP is mocked with respx."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from strixnoapi.proxy.credentials import OAuth
from strixnoapi.proxy.settings import ProxySettings
from strixnoapi.proxy.translators.claude_code import ClaudeCodeTranslator
from strixnoapi.proxy.translators.gemini import GeminiTranslator


@pytest.fixture
def settings(tmp_path: Path):
    return ProxySettings(port=0, token="t", cli_mode="test", audit_dir=tmp_path)


@pytest.fixture
def claude_oauth():
    return OAuth(cli="claude", access_token="ct-test", refresh_token="rt-test", extra={})


@pytest.fixture
def gemini_oauth():
    return OAuth(cli="gemini", access_token="gt-test", extra={})


@pytest.mark.asyncio
@respx.mock
async def test_claude_complete_basic(settings, claude_oauth):
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "hello from claude"}],
                "model": "claude-sonnet-4-6",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 7, "output_tokens": 4},
            },
        )
    )
    t = ClaudeCodeTranslator()
    body = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
    }
    result = await t.complete_openai(body, claude_oauth, settings)
    assert result["choices"][0]["message"]["content"] == "hello from claude"
    assert result["usage"]["prompt_tokens"] == 7
    assert result["usage"]["completion_tokens"] == 4
    assert result["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
@respx.mock
async def test_claude_complete_with_system(settings, claude_oauth):
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )
    )
    t = ClaudeCodeTranslator()
    body = {
        "messages": [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hi"},
        ]
    }
    await t.complete_openai(body, claude_oauth, settings)
    sent = json.loads(route.calls[0].request.content)
    # Anthropic OAuth only accepts the exact Claude Code system string;
    # caller's system content is wrapped into the user message instead.
    assert sent["system"] == "You are Claude Code, Anthropic's official CLI for Claude."
    first_user = next(m for m in sent["messages"] if m["role"] == "user")
    # content is now a block list so we can attach cache_control to the strix_system block
    blocks = first_user["content"]
    assert isinstance(blocks, list)
    strix_block = blocks[0]
    assert strix_block["type"] == "text"
    assert "<strix_system>" in strix_block["text"]
    assert "be helpful" in strix_block["text"]
    assert strix_block["cache_control"] == {"type": "ephemeral"}
    assert any("hi" in b.get("text", "") for b in blocks[1:])


@pytest.mark.asyncio
@respx.mock
async def test_claude_401_returns_clear_error(settings, claude_oauth):
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(401, json={"error": "unauth"})
    )
    t = ClaudeCodeTranslator()
    with pytest.raises(Exception) as exc:
        await t.complete_openai(
            {"messages": [{"role": "user", "content": "hi"}]},
            claude_oauth,
            settings,
        )
    assert "refresh" in str(exc.value).lower() or "401" in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_gemini_complete_basic(settings, gemini_oauth):
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-pro:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "from gemini"}], "role": "model"}}
                ],
                "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2},
            },
        )
    )
    t = GeminiTranslator()
    body = {"messages": [{"role": "user", "content": "hi"}]}
    result = await t.complete_openai(body, gemini_oauth, settings)
    assert result["choices"][0]["message"]["content"] == "from gemini"
    assert result["usage"]["prompt_tokens"] == 3
