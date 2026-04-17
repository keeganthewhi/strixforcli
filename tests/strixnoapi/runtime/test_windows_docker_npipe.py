"""Windows Docker SDK npipesocket chunked-send patch."""

from __future__ import annotations

import sys

import pytest

from strixnoapi.runtime import windows_docker_npipe


def test_coerce_bytes_passthrough():
    assert windows_docker_npipe._coerce_bytes(b"abc") == b"abc"


def test_coerce_bytes_bytearray():
    assert windows_docker_npipe._coerce_bytes(bytearray(b"abc")) == b"abc"


def test_coerce_bytes_memoryview():
    assert windows_docker_npipe._coerce_bytes(memoryview(b"abc")) == b"abc"


def test_coerce_bytes_str():
    assert windows_docker_npipe._coerce_bytes("abc") == b"abc"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only patch")
def test_apply_returns_true_on_first_call(monkeypatch):
    monkeypatch.setattr(windows_docker_npipe, "_APPLIED", False)
    applied = windows_docker_npipe.apply()
    # Either applied or docker SDK not present — both valid on a CI Windows
    # runner without docker-python. If docker is present, must be True.
    try:
        import docker.transport.npipesocket  # noqa: F401
    except ImportError:
        assert not applied
        return
    assert applied


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only patch")
def test_apply_is_idempotent(monkeypatch):
    monkeypatch.setattr(windows_docker_npipe, "_APPLIED", False)
    windows_docker_npipe.apply()
    assert not windows_docker_npipe.apply()


def test_apply_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(windows_docker_npipe, "_APPLIED", False)
    monkeypatch.setattr(sys, "platform", "linux")
    assert not windows_docker_npipe.apply()


def test_apply_respects_skip_env(monkeypatch):
    monkeypatch.setattr(windows_docker_npipe, "_APPLIED", False)
    monkeypatch.setenv("STRIXNOAPI_SKIP_NPIPE_PATCH", "1")
    assert not windows_docker_npipe.apply()
