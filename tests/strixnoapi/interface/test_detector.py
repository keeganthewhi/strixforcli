"""CLI detection logic."""

from __future__ import annotations

import pytest

from strixnoapi.interface import detector
from strixnoapi.interface.detector import detect_all, detect_cli, resolve_cli_mode


@pytest.fixture
def fake_binaries(monkeypatch: pytest.MonkeyPatch):
    """Pretend all four CLI binaries are installed on PATH.

    On CI runners the `claude`, `codex`, `gemini`, `cursor-agent` binaries
    aren't installed — we only need authentication (credential file) to
    test the detection+resolution logic.
    """
    fake_paths = {
        "claude": "/fake/bin/claude",
        "codex": "/fake/bin/codex",
        "gemini": "/fake/bin/gemini",
        "cursor-agent": "/fake/bin/cursor-agent",
        "cursor": "/fake/bin/cursor",
    }
    monkeypatch.setattr(
        detector.shutil,
        "which",
        lambda name: fake_paths.get(name),
    )


def test_detect_nothing(tmp_home, fake_binaries):
    det = detect_cli("claude")
    assert not det.authenticated
    assert det.credential_path is None


def test_detect_claude_authenticated(tmp_home, fake_binaries, claude_creds):
    det = detect_cli("claude")
    assert det.authenticated
    assert det.credential_path == str(claude_creds)


def test_detect_all_partial(tmp_home, fake_binaries, claude_creds, gemini_creds):
    all_det = detect_all()
    assert all_det["claude"].authenticated
    assert all_det["gemini"].authenticated
    assert not all_det["codex"].authenticated
    assert not all_det["cursor"].authenticated


def test_resolve_explicit(tmp_home, fake_binaries, claude_creds):
    assert resolve_cli_mode("claude") == "claude"


def test_resolve_auto_picks_first(tmp_home, fake_binaries, codex_creds, gemini_creds):
    # Detection order is [claude, codex, cursor, gemini], so codex wins
    assert resolve_cli_mode("auto") == "codex"


def test_resolve_invalid(tmp_home, fake_binaries):
    with pytest.raises(ValueError):
        resolve_cli_mode("blahblah")


def test_resolve_auto_no_auth_raises(tmp_home, fake_binaries):
    with pytest.raises(RuntimeError, match="No authenticated"):
        resolve_cli_mode("auto")


def test_detect_requires_binary_on_path(tmp_home, claude_creds, monkeypatch):
    # Without fake_binaries, no CLI binary is on PATH -> installed=False
    monkeypatch.setattr(detector.shutil, "which", lambda _name: None)
    det = detect_cli("claude")
    assert not det.installed
    # Authenticated still reflects credential presence independently
    assert det.authenticated
