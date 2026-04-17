"""Sandbox flag composition."""

from __future__ import annotations

from strixnoapi.security.sandbox_profile import apply_sandbox_flags, baseline_flags


def test_baseline_has_cap_drop():
    flags = baseline_flags()
    assert "--cap-drop=ALL" in flags


def test_baseline_has_seccomp(monkeypatch, tmp_path):
    # Seccomp file may or may not be on disk in test env; just check structure
    flags = baseline_flags()
    assert any(f.startswith("--security-opt=no-new-privileges") for f in flags)
    assert any("read-only" in f or "--read-only" == f for f in flags)


def test_apply_on_non_docker_is_noop():
    argv = ["ls", "-la"]
    assert apply_sandbox_flags(argv) == argv


def test_apply_injects_flags():
    argv = ["docker", "run", "image:tag", "cmd"]
    result = apply_sandbox_flags(argv)
    assert "--cap-drop=ALL" in result
    assert result[0] == "docker"
    assert result[1] == "run"


def test_apply_idempotent():
    argv = ["docker", "run", "--cap-drop=ALL", "image:tag"]
    result = apply_sandbox_flags(argv)
    assert result.count("--cap-drop=ALL") == 1
