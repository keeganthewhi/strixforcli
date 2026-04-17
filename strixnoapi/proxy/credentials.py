"""OAuth credential readers for each supported CLI.

Each reader parses the CLI's native credential file and returns an `OAuth`
dataclass. Reads are re-done on every LLM call (no in-process caching)
so token refresh by the CLI itself is immediately picked up.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OAuth:
    cli: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    account_id: str | None = None
    extra: dict | None = None


class CredentialError(RuntimeError):
    pass


def load_oauth(cli_mode: str) -> OAuth:
    cli_mode = cli_mode.lower()
    if cli_mode == "claude":
        return _load_claude()
    if cli_mode == "codex":
        return _load_codex()
    if cli_mode == "gemini":
        return _load_gemini()
    if cli_mode == "cursor":
        return _load_cursor()
    raise CredentialError(f"unknown cli_mode: {cli_mode!r}")


def _load_claude() -> OAuth:
    path = Path.home() / ".claude" / ".credentials.json"
    _require(path, "Claude Code", "run `claude` to authenticate")
    _check_perms(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    creds = data.get("claudeAiOauth") or data.get("oauth") or data
    token = creds.get("accessToken") or creds.get("access_token")
    if not token:
        raise CredentialError(f"Claude credentials at {path} missing accessToken")
    return OAuth(
        cli="claude",
        access_token=token,
        refresh_token=creds.get("refreshToken") or creds.get("refresh_token"),
        account_id=creds.get("accountUuid") or creds.get("account_id"),
        extra=creds,
    )


def _load_codex() -> OAuth:
    path = Path.home() / ".codex" / "auth.json"
    _require(path, "OpenAI Codex", "run `codex login` to authenticate")
    _check_perms(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    tokens = data.get("tokens", data)
    access = tokens.get("access_token") or tokens.get("id_token") or tokens.get("accessToken")
    if not access:
        raise CredentialError(f"Codex credentials at {path} missing access_token")
    return OAuth(
        cli="codex",
        access_token=access,
        refresh_token=tokens.get("refresh_token"),
        account_id=data.get("account_id") or data.get("user_id"),
        extra=data,
    )


def _load_gemini() -> OAuth:
    path = Path.home() / ".gemini" / "oauth_creds.json"
    _require(path, "Gemini CLI", "run `gemini` to authenticate")
    _check_perms(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    token = data.get("access_token") or data.get("accessToken")
    if not token:
        raise CredentialError(f"Gemini credentials at {path} missing access_token")
    return OAuth(
        cli="gemini",
        access_token=token,
        refresh_token=data.get("refresh_token") or data.get("refreshToken"),
        extra=data,
    )


def _load_cursor() -> OAuth:
    base = Path.home() / ".cursor"
    candidates = [
        base / "cli-config.json",
        base / "auth.json",
        base / "session.json",
    ]
    for path in candidates:
        if path.exists():
            _check_perms(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            token = (
                data.get("access_token")
                or data.get("accessToken")
                or data.get("session_token")
                or data.get("token")
            )
            if token:
                return OAuth(
                    cli="cursor",
                    access_token=token,
                    refresh_token=data.get("refresh_token"),
                    extra=data,
                )
    raise CredentialError(
        f"Cursor credentials not found in {base}. Run `cursor-agent login` to authenticate."
    )


def _require(path: Path, name: str, hint: str) -> None:
    if not path.exists():
        raise CredentialError(f"{name} credentials not found at {path}. {hint}.")


def _check_perms(path: Path) -> None:
    if os.environ.get("STRIX_ENFORCE_PERMISSIONS", "1") != "1":
        return
    if os.name == "nt":
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise CredentialError(
            f"Insecure permissions ({oct(mode)}) on {path}. Run: chmod 600 {path}"
        )
