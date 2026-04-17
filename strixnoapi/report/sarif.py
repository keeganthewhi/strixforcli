"""SARIF 2.1.0 emitter for strix findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
    "master/Schemata/sarif-schema-2.1.0.json"
)


def render_sarif(findings: list[dict[str, Any]], run_dir: Path, run_id: str) -> str:
    rules_by_id: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for f in findings:
        rule_id = _rule_id(f)
        if rule_id not in rules_by_id:
            rules_by_id[rule_id] = {
                "id": rule_id,
                "name": f.get("category") or f.get("type") or rule_id,
                "shortDescription": {"text": f.get("title", rule_id)},
                "fullDescription": {"text": f.get("description", "")},
                "defaultConfiguration": {"level": _severity_to_level(f.get("severity"))},
                "helpUri": f.get("reference_url", ""),
            }
        results.append(
            {
                "ruleId": rule_id,
                "level": _severity_to_level(f.get("severity")),
                "message": {"text": f.get("description") or f.get("title", "")},
                "locations": _locations(f),
                "properties": {
                    "severity": f.get("severity"),
                    "cvss": f.get("cvss"),
                    "cwe": f.get("cwe"),
                },
            }
        )

    sarif = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "strixnoapi",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/usestrix/strix",
                        "rules": list(rules_by_id.values()),
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "workingDirectory": {"uri": run_dir.as_uri()},
                        "properties": {"runId": run_id},
                    }
                ],
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2)


def _rule_id(f: dict[str, Any]) -> str:
    for key in ("rule_id", "id", "category", "type"):
        v = f.get(key)
        if isinstance(v, str) and v:
            return v
    return "strixnoapi.finding"


def _severity_to_level(sev: str | None) -> str:
    if not sev:
        return "warning"
    s = sev.lower()
    if s in ("critical", "high"):
        return "error"
    if s in ("medium", "moderate"):
        return "warning"
    if s in ("low", "info", "informational"):
        return "note"
    return "warning"


def _locations(f: dict[str, Any]) -> list[dict[str, Any]]:
    file = f.get("file") or f.get("path") or f.get("location")
    if not file:
        return []
    line = f.get("line") or f.get("line_number") or 1
    return [
        {
            "physicalLocation": {
                "artifactLocation": {"uri": str(file)},
                "region": {"startLine": int(line) if str(line).isdigit() else 1},
            }
        }
    ]
