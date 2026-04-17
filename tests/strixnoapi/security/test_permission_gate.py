"""File permission gate."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from strixnoapi.security.permission_gate import (
    check_permissions,
    enforce_0o600,
    verify_or_raise,
)


def test_missing_file(tmp_path: Path):
    ok, reason = check_permissions(tmp_path / "nope")
    assert not ok
    assert "does not exist" in reason


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_loose_perms_fail(tmp_path: Path):
    p = tmp_path / "creds.json"
    p.write_text("{}")
    p.chmod(0o644)
    ok, reason = check_permissions(p)
    assert not ok
    assert "loose" in reason


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_tight_perms_pass(tmp_path: Path):
    p = tmp_path / "creds.json"
    p.write_text("{}")
    p.chmod(0o600)
    ok, _ = check_permissions(p)
    assert ok


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_enforce(tmp_path: Path):
    p = tmp_path / "creds.json"
    p.write_text("{}")
    p.chmod(0o644)
    enforce_0o600(p)
    assert (p.stat().st_mode & 0o777) == 0o600


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_verify_or_raise_strict(tmp_path: Path, monkeypatch):
    p = tmp_path / "creds.json"
    p.write_text("{}")
    p.chmod(0o644)
    monkeypatch.setenv("STRIX_ENFORCE_PERMISSIONS", "1")
    with pytest.raises(PermissionError):
        verify_or_raise(p)


def test_verify_or_raise_disabled(tmp_path: Path, monkeypatch):
    p = tmp_path / "creds.json"
    p.write_text("{}")
    monkeypatch.setenv("STRIX_ENFORCE_PERMISSIONS", "0")
    verify_or_raise(p)  # should not raise
