"""Claude streaming translator — event-type coverage."""

from __future__ import annotations

import json

from strixnoapi.proxy.translators.claude_code import ClaudeCodeTranslator


def _decode_chunk(chunk: str) -> dict:
    assert chunk.startswith("data: ")
    raw = chunk.removeprefix("data: ").strip()
    if raw == "[DONE]":
        return {"_sentinel": "DONE"}
    return json.loads(raw)


def test_message_start_yields_role_opening():
    t = ClaudeCodeTranslator()
    chunk = t._translate_stream_event(
        {"type": "message_start", "message": {"role": "assistant"}},
        model="claude-sonnet-4-6",
        chat_id="chat-1",
    )
    assert chunk is not None
    data = _decode_chunk(chunk)
    assert data["choices"][0]["delta"] == {"role": "assistant", "content": ""}


def test_text_delta_yields_content():
    t = ClaudeCodeTranslator()
    chunk = t._translate_stream_event(
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}},
        model="m",
        chat_id="c",
    )
    data = _decode_chunk(chunk)
    assert data["choices"][0]["delta"]["content"] == "hello"


def test_thinking_delta_yields_content():
    t = ClaudeCodeTranslator()
    chunk = t._translate_stream_event(
        {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "reasoning..."}},
        model="m",
        chat_id="c",
    )
    data = _decode_chunk(chunk)
    assert data["choices"][0]["delta"]["content"] == "reasoning..."


def test_tool_use_block_start_emits_invoke_xml():
    t = ClaudeCodeTranslator()
    chunk = t._translate_stream_event(
        {
            "type": "content_block_start",
            "content_block": {"type": "tool_use", "name": "terminal", "id": "x"},
        },
        model="m",
        chat_id="c",
    )
    data = _decode_chunk(chunk)
    assert '<invoke name="terminal">' in data["choices"][0]["delta"]["content"]


def test_content_block_stop_emits_closing_invoke():
    t = ClaudeCodeTranslator()
    chunk = t._translate_stream_event(
        {"type": "content_block_stop"}, model="m", chat_id="c"
    )
    data = _decode_chunk(chunk)
    assert "</invoke>" in data["choices"][0]["delta"]["content"]


def test_message_stop_yields_none():
    t = ClaudeCodeTranslator()
    assert t._translate_stream_event({"type": "message_stop"}, model="m", chat_id="c") is None


def test_message_delta_yields_none():
    t = ClaudeCodeTranslator()
    assert t._translate_stream_event(
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
        model="m",
        chat_id="c",
    ) is None


def test_error_event_surfaces_inline():
    t = ClaudeCodeTranslator()
    chunk = t._translate_stream_event(
        {"type": "error", "error": {"message": "boom"}}, model="m", chat_id="c"
    )
    data = _decode_chunk(chunk)
    assert "boom" in data["choices"][0]["delta"]["content"]


def test_unknown_event_ignored():
    t = ClaudeCodeTranslator()
    assert t._translate_stream_event({"type": "ping"}, model="m", chat_id="c") is None
    assert t._translate_stream_event({"type": "future_kind"}, model="m", chat_id="c") is None


def test_input_json_delta_yields_content():
    t = ClaudeCodeTranslator()
    chunk = t._translate_stream_event(
        {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": '{"k":'}},
        model="m",
        chat_id="c",
    )
    data = _decode_chunk(chunk)
    assert data["choices"][0]["delta"]["content"] == '{"k":'
