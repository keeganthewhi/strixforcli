"""Wrap module — env injection behavior."""

from __future__ import annotations

import pytest

from strixnoapi.wrap import install_proxy


def test_noop_without_cli_mode(monkeypatch):
    monkeypatch.delenv("STRIX_CLI_MODE", raising=False)
    assert install_proxy() is None


def test_noop_with_api_mode(monkeypatch):
    monkeypatch.setenv("STRIX_CLI_MODE", "api")
    assert install_proxy() is None


def test_auto_requires_at_least_one_cli(tmp_home, monkeypatch):
    monkeypatch.setenv("STRIX_CLI_MODE", "auto")
    with pytest.raises(RuntimeError):
        install_proxy()
