"""`strix report <run-id>` — export findings as SARIF / HTML / Markdown."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from strixnoapi.report.html import render_html
from strixnoapi.report.sarif import render_sarif


if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="strix report", description="export scan findings")
    parser.add_argument("run_id", help="run id under strix_runs/")
    parser.add_argument(
        "--format",
        choices=["sarif", "html", "markdown"],
        default="sarif",
        help="output format",
    )
    parser.add_argument("--output", help="output path (default: stdout)")
    args = parser.parse_args(argv)

    console = Console()
    runs_root = Path(os.environ.get("STRIX_RUNS_DIR") or Path.cwd() / "strix_runs")
    run_dir = runs_root / args.run_id
    if not run_dir.exists():
        console.print(f"[red]run not found: {run_dir}[/]")
        return 1

    findings = _load_findings(run_dir)

    if args.format == "sarif":
        content = render_sarif(findings, run_dir, run_id=args.run_id)
    elif args.format == "html":
        content = render_html(findings, run_dir, run_id=args.run_id)
    else:
        content = _load_markdown(run_dir)

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        console.print(f"[green]Wrote {args.format} to {args.output}[/]")
    else:
        print(content)
    return 0


def _load_findings(run_dir: Path) -> list[dict]:
    findings_file = run_dir / "findings.json"
    if findings_file.exists():
        import json

        try:
            data = json.loads(findings_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("findings"), list):
                return data["findings"]
        except json.JSONDecodeError:
            pass
    # Fallback: scan for any *.json in vulnerabilities/
    vulns_dir = run_dir / "vulnerabilities"
    findings: list[dict] = []
    if vulns_dir.exists():
        for f in vulns_dir.glob("*.json"):
            try:
                findings.append(__import__("json").loads(f.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                pass
    return findings


def _load_markdown(run_dir: Path) -> str:
    for name in ("report.md", "REPORT.md", "deliverables/report.md"):
        f = run_dir / name
        if f.exists():
            return f.read_text(encoding="utf-8")
    return f"# Run {run_dir.name}\n\nNo markdown report found.\n"


if __name__ == "__main__":
    sys.exit(main())
