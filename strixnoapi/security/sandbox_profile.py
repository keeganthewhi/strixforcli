"""Hardened docker-run flag sets used when launching the scan sandbox.

These flags are composed by `apply_sandbox_flags()` and can be dropped
into any `docker run` invocation. Upstream strix already runs a
pentester container; we layer our hardening on top via env-var override
(`STRIX_DOCKER_EXTRA_FLAGS`) or by reading our own launcher.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path


SECCOMP_PROFILE_PATH = Path(__file__).resolve().parents[2] / "containers" / "seccomp.json"


def baseline_flags() -> list[str]:
    flags = [
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--read-only",
        "--tmpfs=/tmp:rw,size=1g,mode=1777",
        "--tmpfs=/workspace/.cache:rw,size=512m",
        "--pids-limit=512",
        "--memory=4g",
        "--memory-swap=4g",
    ]
    if SECCOMP_PROFILE_PATH.exists():
        flags.append(f"--security-opt=seccomp={SECCOMP_PROFILE_PATH}")
    # Add NET_RAW only if user explicitly opts in — most of strix's pentest
    # tools (nmap's advanced modes, raw-socket probes) need it.
    if os.environ.get("STRIX_ALLOW_NET_RAW", "1") == "1":
        flags.append("--cap-add=NET_RAW")
        flags.append("--cap-add=NET_ADMIN")
    return flags


def apply_sandbox_flags(argv: list[str]) -> list[str]:
    """Given a `docker run ...` argv, inject baseline hardening flags."""
    if not argv or argv[0] != "docker":
        return argv
    if "run" not in argv[:3]:
        return argv
    out = list(argv)
    insert_at = out.index("run") + 1
    for flag in baseline_flags():
        if flag not in out:
            out.insert(insert_at, flag)
            insert_at += 1
    return out


def format_shell(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)
