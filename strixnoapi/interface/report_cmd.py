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
    """Load findings from a strix run directory.

    Strix (upstream) emits `vulnerabilities/vuln-NNNN.md` plus a flat
    `vulnerabilities.csv` index. strixnoapi parses the CSV for an
    authoritative list (severity, id, title, timestamp, file) and then
    pulls richer fields (CWE, CVSS, endpoint, description) from the
    corresponding markdown. Falls back to finer-grained JSON formats if
    present for forward compatibility.
    """
    import json as _json

    findings: list[dict] = []
    csv_path = run_dir / "vulnerabilities.csv"
    if csv_path.exists():
        import csv

        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                md_rel = row.get("file", "")
                md_path = run_dir / md_rel if md_rel else None
                parsed = _parse_vuln_markdown(md_path) if md_path and md_path.exists() else {}
                findings.append(
                    {
                        "id": row.get("id") or parsed.get("id") or "",
                        "title": row.get("title") or parsed.get("title") or "",
                        "severity": (row.get("severity") or parsed.get("severity") or "info").lower(),
                        "timestamp": row.get("timestamp") or parsed.get("timestamp") or "",
                        "file": parsed.get("target", ""),
                        "line": parsed.get("line"),
                        "description": parsed.get("description", ""),
                        "evidence": parsed.get("evidence", ""),
                        "cwe": parsed.get("cwe"),
                        "cvss": parsed.get("cvss"),
                        "endpoint": parsed.get("endpoint"),
                        "method": parsed.get("method"),
                    }
                )
        if findings:
            return findings

    # Back-compat: findings.json / vulnerabilities/*.json
    findings_file = run_dir / "findings.json"
    if findings_file.exists():
        try:
            data = _json.loads(findings_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("findings"), list):
                return data["findings"]
        except _json.JSONDecodeError:
            pass
    vulns_dir = run_dir / "vulnerabilities"
    if vulns_dir.exists():
        for f in vulns_dir.glob("*.json"):
            try:
                findings.append(_json.loads(f.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                pass
    return findings


def _parse_vuln_markdown(md_path: Path) -> dict:
    """Extract structured fields from a strix vuln-NNNN.md file."""
    import re

    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    out: dict = {}
    title_m = re.match(r"^# +(.+?)\s*\n", text)
    if title_m:
        out["title"] = title_m.group(1).strip()

    # Key-value lines of the form "**Key:** value"
    for key in ("ID", "Severity", "Found", "Target", "Endpoint", "Method", "CWE", "CVSS"):
        m = re.search(rf"^\*\*{key}:\*\*\s*(.+)$", text, flags=re.MULTILINE)
        if m:
            norm = key.lower().replace("found", "timestamp")
            out[norm] = m.group(1).strip()

    # Extract `## Description` through next heading
    desc_m = re.search(r"^## Description\s*\n(.+?)(?=\n## |\Z)", text, flags=re.DOTALL | re.MULTILINE)
    if desc_m:
        out["description"] = desc_m.group(1).strip()

    # Best-effort line hint like ":15" or "line 25" inside the doc
    line_m = re.search(r"\b(?:line|L)\s*(\d+)\b", text, flags=re.IGNORECASE)
    if line_m:
        try:
            out["line"] = int(line_m.group(1))
        except ValueError:
            pass

    return out


def _load_markdown(run_dir: Path) -> str:
    for name in (
        "penetration_test_report.md",
        "report.md",
        "REPORT.md",
        "deliverables/report.md",
    ):
        f = run_dir / name
        if f.exists():
            return f.read_text(encoding="utf-8")
    return f"# Run {run_dir.name}\n\nNo markdown report found.\n"


if __name__ == "__main__":
    sys.exit(main())
