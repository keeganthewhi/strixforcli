"""CLI detection logic."""

from __future__ import annotations

import pytest

from strixnoapi.interface.detector import detect_all, detect_cli, resolve_cli_mode


def test_detect_nothing(tmp_home):
    det = detect_cli("claude")
    assert not det.authenticated
    assert det.credential_path is None


def test_detect_claude_authenticated(tmp_home, claude_creds):
    det = detect_cli("claude")
    assert det.authenticated
    assert det.credential_path == str(claude_creds)


def test_detect_all_partial(tmp_home, claude_creds, gemini_creds):
    all_det = detect_all()
    assert all_det["claude"].authenticated
    assert all_det["gemini"].authenticated
    assert not all_det["codex"].authenticated
    assert not all_det["cursor"].authenticated


def test_resolve_explicit(tmp_home, claude_creds):
    assert resolve_cli_mode("claude") == "claude"


def test_resolve_auto_picks_first(tmp_home, codex_creds, gemini_creds):
    # Detection order is [claude, codex, cursor, gemini], so codex wins
    assert resolve_cli_mode("auto") == "codex"


def test_resolve_invalid(tmp_home):
    with pytest.raises(ValueError):
        resolve_cli_mode("blahblah")


def test_resolve_auto_no_auth_raises(tmp_home):
    with pytest.raises(RuntimeError, match="No authenticated"):
        resolve_cli_mode("auto")
