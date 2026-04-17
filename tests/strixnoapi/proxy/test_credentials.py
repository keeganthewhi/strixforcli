"""Credential file parsers."""

from __future__ import annotations

import pytest

from strixnoapi.proxy.credentials import CredentialError, load_oauth


def test_load_claude(claude_creds):
    oauth = load_oauth("claude")
    assert oauth.cli == "claude"
    assert oauth.access_token == "sk-ant-oat-test-token-do-not-use"
    assert oauth.refresh_token == "refresh-abc"
    assert oauth.account_id == "test-acct"


def test_load_codex(codex_creds):
    oauth = load_oauth("codex")
    assert oauth.cli == "codex"
    assert oauth.access_token.startswith("eyJ")
    assert oauth.account_id == "acct-test"


def test_load_gemini(gemini_creds):
    oauth = load_oauth("gemini")
    assert oauth.cli == "gemini"
    assert oauth.access_token.startswith("ya29.")


def test_load_cursor(cursor_creds):
    oauth = load_oauth("cursor")
    assert oauth.cli == "cursor"
    assert oauth.access_token == "cursor-test-session"


def test_missing_claude(tmp_home):
    with pytest.raises(CredentialError, match="Claude"):
        load_oauth("claude")


def test_unknown_cli():
    with pytest.raises(CredentialError, match="unknown"):
        load_oauth("blah")
