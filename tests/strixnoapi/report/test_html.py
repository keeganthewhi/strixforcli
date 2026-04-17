"""HTML emitter."""

from __future__ import annotations

from pathlib import Path

from strixnoapi.report.html import render_html


def test_header(tmp_path: Path):
    html = render_html([], tmp_path, run_id="r-42")
    assert "<!doctype html>" in html
    assert "r-42" in html
    assert "strixnoapi" in html


def test_renders_findings(tmp_path: Path):
    findings = [
        {
            "title": "Open redirect",
            "severity": "medium",
            "description": "Arbitrary URL accepted",
            "evidence": "curl https://app/redirect?u=evil",
            "location": "src/redirect.py",
        }
    ]
    html = render_html(findings, tmp_path, run_id="r1")
    assert "Open redirect" in html
    assert "Arbitrary URL accepted" in html
    assert "evil" in html
    assert "sev-medium" in html


def test_escapes_html(tmp_path: Path):
    findings = [{"title": "<script>alert(1)</script>", "severity": "low"}]
    html = render_html(findings, tmp_path, run_id="r")
    assert "<script>" not in html.replace("<script>alert(1)</script>", "")
    assert "&lt;script&gt;" in html
