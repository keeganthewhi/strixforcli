"""`strix version` — emit full version + environment info."""

from __future__ import annotations

import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Sequence


def _pkg_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


UPSTREAM_STRIX_BASE_SHA = "15c95718e600897a2a532a613a1c8fa6b712b144"
UPSTREAM_STRIX_BASE_VERSION = "0.8.3"


def main(argv: Sequence[str] | None = None) -> int:  # noqa: ARG001
    from strixnoapi.interface.detector import detect_all

    print(f"strixnoapi  {_pkg_version('strixnoapi')}")
    upstream_installed = _pkg_version("strix-agent")
    if upstream_installed == "unknown":
        print(
            f"strix core  vendored from usestrix/strix v{UPSTREAM_STRIX_BASE_VERSION} "
            f"({UPSTREAM_STRIX_BASE_SHA[:7]})"
        )
    else:
        print(f"strix core  {upstream_installed} (upstream)")
    print(f"python      {platform.python_version()}  ({sys.platform})")
    print()

    detections = detect_all()
    print("CLI subscriptions detected:")
    for name, det in detections.items():
        parts = []
        if det.installed:
            parts.append("installed")
        if det.authenticated:
            parts.append("authenticated")
        status = ", ".join(parts) if parts else "not available"
        print(f"  {name:<8} {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
