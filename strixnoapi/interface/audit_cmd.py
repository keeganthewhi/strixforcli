"""`strix audit verify <run-id|path>` — validate hash-chain integrity."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from strixnoapi.proxy.audit import verify_chain


if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strix audit", description="audit log tools")
    sub = parser.add_subparsers(dest="cmd", required=True)
    vsp = sub.add_parser("verify", help="verify the hash chain of an audit log")
    vsp.add_argument("target", help="run-id or absolute path to a .jsonl audit file")
    args = parser.parse_args(argv)

    console = Console()

    path = _resolve_target(args.target)
    if path is None:
        console.print(f"[red]could not locate audit log for {args.target!r}[/]")
        return 1

    ok, n, reason = verify_chain(path)
    if ok:
        console.print(Panel(
            f"[green]Audit chain OK[/]\n"
            f"file: [cyan]{path}[/]\n"
            f"entries verified: [bold]{n}[/]",
            border_style="green",
            padding=(1, 2),
        ))
        return 0
    console.print(Panel(
        f"[red]Audit chain INVALID[/]\n"
        f"file: [cyan]{path}[/]\n"
        f"entries verified before failure: [bold]{n}[/]\n"
        f"reason: [yellow]{reason}[/]",
        border_style="red",
        padding=(1, 2),
    ))
    return 2


def _resolve_target(target: str) -> Path | None:
    p = Path(target)
    if p.exists() and p.is_file():
        return p
    audit_dir = Path.home() / ".strix" / "audit"
    for candidate in audit_dir.glob(f"*{target}*.jsonl"):
        return candidate
    # Look inside run dirs
    for runs_root in (Path.cwd() / "strix_runs", Path.home() / ".strix" / "runs"):
        run = runs_root / target
        if run.exists():
            for candidate in run.rglob("*.jsonl"):
                return candidate
    return None


if __name__ == "__main__":
    sys.exit(main())
