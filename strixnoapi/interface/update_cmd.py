"""`strix update` — pull latest security patches from upstream strix."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Sequence

from rich.console import Console
from rich.panel import Panel


UPSTREAM_REMOTE = "upstream"
UPSTREAM_BRANCH = "main"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strix update", description="sync security patches from upstream strix")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list commits that would be pulled without merging",
    )
    args = parser.parse_args(argv)

    console = Console()

    result = subprocess.run(
        ["git", "remote", "-v"],
        capture_output=True,
        text=True,
        check=False,
    )
    if UPSTREAM_REMOTE not in result.stdout:
        console.print(Panel(
            f"[yellow]No '{UPSTREAM_REMOTE}' git remote configured.\n"
            f"Run: git remote add {UPSTREAM_REMOTE} https://github.com/usestrix/strix.git",
            border_style="yellow",
            padding=(1, 2),
        ))
        return 1

    subprocess.run(["git", "fetch", UPSTREAM_REMOTE, UPSTREAM_BRANCH], check=True)

    log = subprocess.run(
        ["git", "log", "--oneline", f"HEAD..{UPSTREAM_REMOTE}/{UPSTREAM_BRANCH}"],
        capture_output=True,
        text=True,
        check=False,
    )
    pending = log.stdout.strip()
    if not pending:
        console.print("[green]Already up to date with upstream.[/]")
        return 0

    console.print(f"[cyan]Commits available on {UPSTREAM_REMOTE}/{UPSTREAM_BRANCH}:[/]")
    console.print(pending)

    if args.dry_run:
        return 0

    console.print(Panel(
        "[yellow]Review the commits above, then merge manually:\n\n"
        f"  git merge {UPSTREAM_REMOTE}/{UPSTREAM_BRANCH}\n\n"
        "Upstream changes that touch strixnoapi/ should be inspected before merging.\n"
        "Use 'git log -p <commit> -- strix/' to preview.",
        border_style="yellow",
        padding=(1, 2),
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
