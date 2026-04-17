"""Request-body validation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from strixnoapi.proxy.validation import flatten_text, validate_request_body


MAX_PROMPT = 2 * 1024 * 1024
MAX_MSG = 256 * 1024


def test_valid_simple_body():
    body = {"messages": [{"role": "user", "content": "hello"}]}
    validate_request_body(body, MAX_PROMPT, MAX_MSG)


def test_rejects_missing_messages():
    with pytest.raises(HTTPException) as exc:
        validate_request_body({}, MAX_PROMPT, MAX_MSG)
    assert exc.value.status_code == 400


def test_rejects_empty_messages():
    with pytest.raises(HTTPException):
        validate_request_body({"messages": []}, MAX_PROMPT, MAX_MSG)


def test_rejects_invalid_role():
    with pytest.raises(HTTPException) as exc:
        validate_request_body(
            {"messages": [{"role": "wizard", "content": "hi"}]},
            MAX_PROMPT,
            MAX_MSG,
        )
    assert exc.value.status_code == 400


def test_rejects_oversized_prompt():
    big = "x" * (MAX_MSG + 100)
    with pytest.raises(HTTPException) as exc:
        validate_request_body(
            {"messages": [{"role": "user", "content": big}]},
            MAX_PROMPT,
            MAX_MSG,
        )
    assert exc.value.status_code == 413


def test_rejects_control_chars():
    with pytest.raises(HTTPException):
        validate_request_body(
            {"messages": [{"role": "user", "content": "hi\x01there"}]},
            MAX_PROMPT,
            MAX_MSG,
        )


def test_allows_newlines_and_tabs():
    validate_request_body(
        {"messages": [{"role": "user", "content": "line1\nline2\tcol"}]},
        MAX_PROMPT,
        MAX_MSG,
    )


def test_flatten_text_simple():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert flatten_text(msgs) == "sys\nhi\nhello"


def test_flatten_text_blocks():
    msgs = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "first"}, {"type": "text", "text": "second"}],
        }
    ]
    assert flatten_text(msgs) == "first\nsecond"
