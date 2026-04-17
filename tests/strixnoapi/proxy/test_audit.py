"""Audit log hash-chain integrity."""

from __future__ import annotations

import json
from pathlib import Path

from strixnoapi.proxy.audit import GENESIS_HASH, AuditLogger, verify_chain


def test_genesis_chain(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    with AuditLogger(path) as log:
        h1 = log.append({"kind": "req", "n": 1})
        h2 = log.append({"kind": "req", "n": 2})
        h3 = log.append({"kind": "req", "n": 3})
    assert h1 != h2 != h3
    assert len(h1) == 64

    ok, n, reason = verify_chain(path)
    assert ok, reason
    assert n == 3


def test_each_entry_references_previous(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    with AuditLogger(path) as log:
        log.append({"kind": "a"})
        log.append({"kind": "b"})
        log.append({"kind": "c"})
    entries = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert entries[0]["prev_hash"] == GENESIS_HASH
    assert entries[1]["prev_hash"] == entries[0]["hash"]
    assert entries[2]["prev_hash"] == entries[1]["hash"]


def test_tamper_is_detected(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    with AuditLogger(path) as log:
        log.append({"kind": "a"})
        log.append({"kind": "b"})
        log.append({"kind": "c"})
    # Tamper with middle entry
    lines = path.read_text().splitlines()
    lines[1] = lines[1].replace('"b"', '"EVIL"')
    path.write_text("\n".join(lines) + "\n")
    ok, _, reason = verify_chain(path)
    assert not ok
    assert "hash mismatch" in reason or "prev_hash" in reason


def test_append_resumes_from_existing(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    with AuditLogger(path) as log:
        h_a = log.append({"kind": "a"})
    # New logger picks up where we left off
    with AuditLogger(path) as log:
        h_b = log.append({"kind": "b"})
    entries = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert entries[0]["hash"] == h_a
    assert entries[1]["prev_hash"] == h_a
    assert entries[1]["hash"] == h_b
    ok, n, _ = verify_chain(path)
    assert ok
    assert n == 2


def test_missing_file(tmp_path: Path):
    ok, n, reason = verify_chain(tmp_path / "nope.jsonl")
    assert not ok
    assert reason is not None
    assert n == 0
