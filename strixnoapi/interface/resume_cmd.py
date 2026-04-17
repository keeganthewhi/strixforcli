"""`strix resume <run-id>` — continue an interrupted scan from last checkpoint."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from rich.console import Console
from rich.panel import Panel

from strixnoapi.checkpoint.reader import load_latest_checkpoint


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strix resume", description="resume an interrupted scan")
    parser.add_argument("run_id", help="run identifier (directory under strix_runs/)")
    parser.add_argument("--list", action="store_true", help="list available runs instead")
    args = parser.parse_args(argv)

    console = Console()
    runs_root = Path(os.environ.get("STRIX_RUNS_DIR") or Path.cwd() / "strix_runs")

    if args.list or args.run_id == "list":
        if not runs_root.exists():
            console.print(f"[yellow]No runs directory at {runs_root}[/]")
            return 0
        for d in sorted(runs_root.iterdir()):
            if d.is_dir():
                ck = d / "checkpoints"
                n = len(list(ck.glob("*.zst"))) if ck.exists() else 0
                console.print(f"  {d.name}  (checkpoints: {n})")
        return 0

    run_dir = runs_root / args.run_id
    if not run_dir.exists():
        console.print(Panel(f"[red]Run not found: {run_dir}", border_style="red", padding=(1, 2)))
        return 1

    cp = load_latest_checkpoint(run_dir)
    if cp is None:
        console.print(Panel(
            f"[yellow]No checkpoint found for run {args.run_id}. Nothing to resume.",
            border_style="yellow",
            padding=(1, 2),
        ))
        return 1

    os.environ["STRIX_RESUME_FROM"] = str(cp.path)
    os.environ.setdefault("STRIX_RUN_ID", args.run_id)
    console.print(Panel(
        f"[green]Resuming run [bold]{args.run_id}[/] from phase [bold]{cp.phase}[/]\n"
        f"checkpoint: [cyan]{cp.path}[/]",
        border_style="green",
        padding=(1, 2),
    ))

    from strixnoapi.wrap import install_proxy

    install_proxy()
    from strix.interface.main import main as upstream_main

    upstream_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
