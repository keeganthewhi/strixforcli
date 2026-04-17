"""CLI binary + OAuth credential detection."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


DETECTION_ORDER: list[str] = ["claude", "codex", "cursor", "gemini"]

BINARY: dict[str, list[str]] = {
    "claude": ["claude"],
    "codex": ["codex"],
    "gemini": ["gemini"],
    "cursor": ["cursor-agent", "cursor"],
}

CRED_PATHS: dict[str, list[Path]] = {
    "claude": [Path.home() / ".claude" / ".credentials.json"],
    "codex": [Path.home() / ".codex" / "auth.json"],
    "gemini": [Path.home() / ".gemini" / "oauth_creds.json"],
    "cursor": [
        Path.home() / ".cursor" / "cli-config.json",
        Path.home() / ".cursor" / "auth.json",
        Path.home() / ".cursor" / "session.json",
    ],
}


@dataclass(frozen=True)
class CliDetection:
    cli: str
    installed: bool
    binary_path: str | None
    authenticated: bool
    credential_path: str | None
    version: str | None = None
    issue: str | None = None


def detect_cli(name: str) -> CliDetection:
    binary_path = None
    for candidate in BINARY.get(name, []):
        which = shutil.which(candidate)
        if which:
            binary_path = which
            break
    cred_path = None
    for candidate in CRED_PATHS.get(name, []):
        if candidate.exists():
            cred_path = candidate
            break
    authenticated = cred_path is not None
    issue: str | None = None
    if authenticated and cred_path is not None:
        try:
            json.loads(cred_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            authenticated = False
            issue = f"credential file at {cred_path} unreadable: {e}"
    return CliDetection(
        cli=name,
        installed=binary_path is not None,
        binary_path=binary_path,
        authenticated=authenticated,
        credential_path=str(cred_path) if cred_path else None,
        issue=issue,
    )


def detect_all() -> dict[str, CliDetection]:
    return {name: detect_cli(name) for name in DETECTION_ORDER}


def resolve_cli_mode(requested: str) -> str:
    requested = requested.lower().strip()
    if requested == "auto":
        for name in DETECTION_ORDER:
            d = detect_cli(name)
            if d.installed and d.authenticated:
                return name
        msg = "No authenticated CLI detected. Run `claude`, `codex login`, `cursor-agent login`, or `gemini` first."
        raise RuntimeError(msg)
    if requested in {"claude", "codex", "gemini", "cursor"}:
        return requested
    msg = f"Invalid STRIX_CLI_MODE: {requested!r}"
    raise ValueError(msg)
