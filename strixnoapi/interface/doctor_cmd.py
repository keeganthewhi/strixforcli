"""`strix doctor` — preflight diagnostics before running a scan."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from strixnoapi.interface.detector import detect_all
from strixnoapi.security.permission_gate import check_permissions


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strix doctor", description="strixnoapi diagnostics")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)

    checks: list[tuple[str, bool, str]] = []

    checks.append(_check_python())
    checks.append(_check_docker())
    checks.append(_check_port())
    checks.append(_check_clis())
    checks.append(_check_config_permissions())
    checks.append(_check_disk_space())

    ok = all(passed for _, passed, _ in checks)

    if args.json:
        import json

        payload = {
            "ok": ok,
            "checks": [
                {"name": name, "ok": passed, "detail": detail} for name, passed, detail in checks
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0 if ok else 1

    console = Console()
    table = Table(title="strix doctor")
    table.add_column("Check", style="bold cyan")
    table.add_column("Status")
    table.add_column("Detail")
    for name, passed, detail in checks:
        status = "[green]ok[/]" if passed else "[red]FAIL[/]"
        table.add_row(name, status, detail)
    console.print(table)
    if ok:
        console.print(Panel(
            "[green]All checks passed. strixnoapi is ready.",
            border_style="green",
            padding=(1, 2),
        ))
    else:
        console.print(Panel(
            "[red]Some checks failed. Fix the items above before running a scan.",
            border_style="red",
            padding=(1, 2),
        ))
    return 0 if ok else 1


def _check_python() -> tuple[str, bool, str]:
    py = sys.version_info
    ok = py >= (3, 12)
    return ("Python ≥ 3.12", ok, f"{py.major}.{py.minor}.{py.micro}")


def _check_docker() -> tuple[str, bool, str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return ("Docker CLI on PATH", False, "not found")
    try:
        import docker as docker_sdk

        client = docker_sdk.from_env(timeout=5)
        client.ping()
        return ("Docker daemon reachable", True, f"via {docker_bin}")
    except Exception as e:  # noqa: BLE001
        return ("Docker daemon reachable", False, f"{type(e).__name__}: {e}")


def _check_port() -> tuple[str, bool, str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        return ("Ephemeral port bindable", True, f"got port {port}")
    except OSError as e:
        return ("Ephemeral port bindable", False, str(e))


def _check_clis() -> tuple[str, bool, str]:
    det = detect_all()
    authed = [name for name, d in det.items() if d.installed and d.authenticated]
    if authed:
        return ("At least one authenticated CLI", True, ", ".join(authed))
    installed = [name for name, d in det.items() if d.installed]
    detail = "none authenticated"
    if installed:
        detail = f"installed but not authenticated: {', '.join(installed)}"
    return ("At least one authenticated CLI", False, detail)


def _check_config_permissions() -> tuple[str, bool, str]:
    config_path = Path.home() / ".strix" / "cli-config.json"
    if not config_path.exists():
        return ("Config file (~/.strix/cli-config.json)", False, "not found — run `strix setup`")
    ok, reason = check_permissions(config_path)
    return ("Config file permissions 0o600", ok, reason)


def _check_disk_space() -> tuple[str, bool, str]:
    try:
        stat = shutil.disk_usage(Path.home())
        free_gb = stat.free / (1024**3)
        ok = free_gb >= 2.0
        return ("≥ 2 GB free disk", ok, f"{free_gb:.1f} GB free")
    except OSError as e:
        return ("≥ 2 GB free disk", False, str(e))


if __name__ == "__main__":
    sys.exit(main())
