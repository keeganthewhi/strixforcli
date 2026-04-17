"""`strix setup` — interactive wizard to pick + persist a default CLI mode."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from strixnoapi.interface.detector import DETECTION_ORDER, detect_all


if TYPE_CHECKING:
    from collections.abc import Sequence


CONFIG_DIR = Path.home() / ".strix"
CONFIG_PATH = CONFIG_DIR / "cli-config.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strix setup", description="strixnoapi interactive setup")
    parser.add_argument("--auto", action="store_true", help="pick first authenticated CLI automatically")
    parser.add_argument("--cli", choices=["claude", "codex", "cursor", "gemini"], help="force a specific CLI")
    parser.add_argument("--force", action="store_true", help="overwrite existing config")
    args = parser.parse_args(argv)

    console = Console()
    detections = detect_all()
    _print_detection_table(console, detections)

    if CONFIG_PATH.exists() and not args.force and not args.auto and not args.cli:
        console.print(f"\n[yellow]Config already exists at {CONFIG_PATH}. Use --force to overwrite.[/]")
        return 0

    chosen = _choose(args, detections)
    if chosen is None:
        console.print(Panel(
            Text.from_markup(
                "No authenticated CLI detected.\n\n"
                "Install and log in to at least one:\n"
                "  • Claude Code:  [cyan]npm i -g @anthropic-ai/claude-code[/], then [cyan]claude[/]\n"
                "  • OpenAI Codex: [cyan]npm i -g @openai/codex[/], then [cyan]codex login[/]\n"
                "  • Cursor:       [cyan]curl https://cursor.com/install | bash[/], then [cyan]cursor-agent login[/]\n"
                "  • Gemini:       [cyan]npm i -g @google/gemini-cli[/], then [cyan]gemini[/]\n"
            ),
            title="[bold red]strix setup failed",
            border_style="red",
            padding=(1, 2),
        ))
        return 2

    _write_config(chosen, detections)
    console.print(Panel(
        Text.from_markup(
            f"Default CLI mode: [bold green]{chosen}[/]\n"
            f"Config written to: [cyan]{CONFIG_PATH}[/]\n\n"
            f"Next: run [bold cyan]strix doctor[/] to confirm the environment is healthy.\n"
            f"Then: [bold cyan]STRIX_CLI_MODE={chosen} strix --target <url>[/]"
        ),
        title="[bold green]strix setup ok",
        border_style="green",
        padding=(1, 2),
    ))
    return 0


def _choose(args: argparse.Namespace, detections: dict) -> str | None:
    if args.cli:
        return args.cli if detections[args.cli].installed else None
    if args.auto:
        return _first_authenticated(detections)
    candidates = [
        n for n in DETECTION_ORDER
        if detections[n].installed and detections[n].authenticated
    ]
    if not candidates:
        return None
    return _prompt_user(candidates)


def _first_authenticated(detections: dict) -> str | None:
    for name in DETECTION_ORDER:
        if detections[name].installed and detections[name].authenticated:
            return name
    return None


def _prompt_user(candidates: list[str]) -> str:
    try:
        import questionary
    except ImportError:
        print(f"Picking first candidate: {candidates[0]}")
        return candidates[0]
    return questionary.select(
        "Which CLI should strix route LLM calls through by default?",
        choices=candidates,
        default=candidates[0],
    ).ask()


def _print_detection_table(console: Console, detections: dict) -> None:
    table = Table(title="Detected CLI subscriptions", show_lines=False)
    table.add_column("CLI", style="bold cyan")
    table.add_column("Installed")
    table.add_column("Authenticated")
    table.add_column("Binary / credential path")
    for name in DETECTION_ORDER:
        d = detections[name]
        installed = "[green]yes[/]" if d.installed else "[red]no[/]"
        authed = "[green]yes[/]" if d.authenticated else "[red]no[/]"
        path = d.binary_path or "-"
        if d.authenticated:
            path = f"{path}\n{d.credential_path}"
        table.add_row(name, installed, authed, path)
    console.print(table)


def _write_config(chosen: str, detections: dict) -> None:
    CONFIG_DIR.mkdir(mode=0o700, exist_ok=True)
    config = {
        "version": 1,
        "cli_mode": chosen,
        "telemetry": False,
        "proxy": {"rate_limit_rpm": 30, "inactivity_timeout_s": 1800, "log_prompts": False},
        "detected": {
            name: {
                "installed": detections[name].installed,
                "authenticated": detections[name].authenticated,
                "binary_path": detections[name].binary_path,
                "credential_path": detections[name].credential_path,
            }
            for name in DETECTION_ORDER
        },
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    if os.name != "nt":
        os.chmod(CONFIG_PATH, 0o600)


if __name__ == "__main__":
    sys.exit(main())
