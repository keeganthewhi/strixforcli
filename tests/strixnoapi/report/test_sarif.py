"""SARIF emitter."""

from __future__ import annotations

import json
from pathlib import Path

from strixnoapi.report.sarif import SARIF_SCHEMA, SARIF_VERSION, render_sarif


def test_minimal_empty(tmp_path: Path):
    out = render_sarif([], tmp_path, run_id="r1")
    data = json.loads(out)
    assert data["version"] == SARIF_VERSION
    assert data["$schema"] == SARIF_SCHEMA
    assert data["runs"][0]["tool"]["driver"]["name"] == "strixnoapi"
    assert data["runs"][0]["results"] == []


def test_finding_rendered(tmp_path: Path):
    findings = [
        {
            "id": "SQLi-1",
            "category": "sqli",
            "title": "SQL Injection in login",
            "description": "Unescaped user input flows to SQL query",
            "severity": "high",
            "file": "src/login.py",
            "line": 42,
        }
    ]
    out = render_sarif(findings, tmp_path, run_id="r1")
    data = json.loads(out)
    results = data["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["level"] == "error"
    assert results[0]["message"]["text"] == findings[0]["description"]
    locations = results[0]["locations"]
    assert locations[0]["physicalLocation"]["artifactLocation"]["uri"] == "src/login.py"
    assert locations[0]["physicalLocation"]["region"]["startLine"] == 42


def test_severity_mapping(tmp_path: Path):
    findings = [
        {"id": "a", "severity": "critical"},
        {"id": "b", "severity": "medium"},
        {"id": "c", "severity": "info"},
    ]
    out = render_sarif(findings, tmp_path, run_id="r1")
    data = json.loads(out)
    levels = [r["level"] for r in data["runs"][0]["results"]]
    assert levels == ["error", "warning", "note"]


def test_rules_deduplicated(tmp_path: Path):
    findings = [
        {"id": "same-rule", "title": "One", "severity": "low"},
        {"id": "same-rule", "title": "Two", "severity": "low"},
    ]
    out = render_sarif(findings, tmp_path, run_id="r1")
    data = json.loads(out)
    rules = data["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 1
