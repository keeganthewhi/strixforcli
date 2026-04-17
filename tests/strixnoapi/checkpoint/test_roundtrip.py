"""Checkpoint write/read round trip."""

from __future__ import annotations

from pathlib import Path

from strixnoapi.checkpoint.reader import (
    extract_checkpoint,
    load_latest_checkpoint,
    read_meta,
)
from strixnoapi.checkpoint.writer import write_checkpoint


def test_roundtrip(tmp_path: Path):
    run_dir = tmp_path / "test-run"
    run_dir.mkdir()
    state_dir = run_dir / "state"
    state_dir.mkdir()
    (state_dir / "progress.txt").write_text("phase=recon\n")
    (state_dir / "findings.json").write_text("[]")

    ck_path = write_checkpoint(run_dir, phase="recon", source_dirs=[state_dir])
    assert ck_path.exists()
    assert ck_path.suffix == ".zst"

    meta = read_meta(ck_path)
    assert meta.phase == "recon"
    assert meta.run_id == "test-run"
    assert meta.version == 1


def test_latest(tmp_path: Path):
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    (run_dir / "a.txt").write_text("a")
    write_checkpoint(run_dir, phase="1", source_dirs=[run_dir])
    (run_dir / "b.txt").write_text("b")
    write_checkpoint(run_dir, phase="2", source_dirs=[run_dir])

    latest = load_latest_checkpoint(run_dir)
    assert latest is not None
    assert latest.phase == "2"


def test_extract(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    payload = run_dir / "payload.txt"
    payload.write_text("important state")
    ck = write_checkpoint(run_dir, phase="1", source_dirs=[run_dir])

    dest = tmp_path / "restored"
    extract_checkpoint(ck, dest)
    # Extracted content lives under dest/run/payload.txt (tar archives the dir name)
    assert (dest / "run" / "payload.txt").read_text() == "important state"


def test_load_latest_none(tmp_path: Path):
    run_dir = tmp_path / "empty"
    run_dir.mkdir()
    assert load_latest_checkpoint(run_dir) is None
