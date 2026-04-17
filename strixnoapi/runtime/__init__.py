"""Runtime compatibility shims applied before upstream strix runs.

These are monkeypatches for known upstream / Windows / dependency bugs
that block strixnoapi's scans. They are applied from `strixnoapi.wrap`
right after proxy boot and only when their preconditions are met.

Each shim lives in its own module so it's opt-in and independently
testable. The top-level `apply_runtime_fixes()` is called once per
process and is idempotent.
"""

from __future__ import annotations


__all__ = ["apply_runtime_fixes"]


def apply_runtime_fixes() -> None:
    """Apply every runtime shim whose preconditions are met."""
    from strixnoapi.runtime import windows_docker_npipe

    windows_docker_npipe.apply()
