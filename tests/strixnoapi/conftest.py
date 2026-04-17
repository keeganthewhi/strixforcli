"""Shared pytest fixtures for strixnoapi tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate Path.home() to a temp dir for each test."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def claude_creds(tmp_home: Path) -> Path:
    d = tmp_home / ".claude"
    d.mkdir(mode=0o700)
    path = d / ".credentials.json"
    path.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": "sk-ant-oat-test-token-do-not-use",
                    "refreshToken": "refresh-abc",
                    "accountUuid": "test-acct",
                }
            }
        ),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


@pytest.fixture
def codex_creds(tmp_home: Path) -> Path:
    d = tmp_home / ".codex"
    d.mkdir(mode=0o700)
    path = d / "auth.json"
    path.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": "eyJ.test-codex.token",
                    "refresh_token": "r-codex",
                },
                "account_id": "acct-test",
            }
        ),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


@pytest.fixture
def gemini_creds(tmp_home: Path) -> Path:
    d = tmp_home / ".gemini"
    d.mkdir(mode=0o700)
    path = d / "oauth_creds.json"
    path.write_text(
        json.dumps(
            {
                "access_token": "ya29.test-gemini-token",
                "refresh_token": "r-gemini",
            }
        ),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


@pytest.fixture
def cursor_creds(tmp_home: Path) -> Path:
    d = tmp_home / ".cursor"
    d.mkdir(mode=0o700)
    path = d / "cli-config.json"
    path.write_text(
        json.dumps({"access_token": "cursor-test-session"}),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


@pytest.fixture(autouse=True)
def disable_perm_enforcement_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows can't set 0o600 portably; don't enforce in tests."""
    if os.name == "nt":
        monkeypatch.setenv("STRIX_ENFORCE_PERMISSIONS", "0")
