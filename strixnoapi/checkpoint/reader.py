"""Load zstd checkpoints written by `writer.write_checkpoint`."""

from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path

import zstandard as zstd


@dataclass(frozen=True)
class Checkpoint:
    path: Path
    version: int
    run_id: str
    phase: str
    created_ts: float


def _open_tar(path: Path) -> tarfile.TarFile:
    dctx = zstd.ZstdDecompressor()
    stream = dctx.stream_reader(path.open("rb"))
    # Buffer fully into memory: checkpoints are small (MB scale).
    data = stream.read()
    return tarfile.open(fileobj=io.BytesIO(data), mode="r:")


def read_meta(path: Path) -> Checkpoint:
    with _open_tar(path) as tar:
        try:
            member = tar.getmember("CHECKPOINT_META.json")
            fh = tar.extractfile(member)
            assert fh is not None
            raw = fh.read()
        except KeyError as e:
            msg = f"checkpoint {path} missing CHECKPOINT_META.json"
            raise ValueError(msg) from e
    meta = json.loads(raw.decode("utf-8"))
    return Checkpoint(
        path=path,
        version=int(meta.get("version", 1)),
        run_id=str(meta.get("run_id", "")),
        phase=str(meta.get("phase", "")),
        created_ts=float(meta.get("created_ts", 0.0)),
    )


def load_latest_checkpoint(run_dir: Path) -> Checkpoint | None:
    ck_dir = run_dir / "checkpoints"
    if not ck_dir.exists():
        return None
    files = sorted(ck_dir.glob("phase_*.tar.zst"), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    return read_meta(files[-1])


def extract_checkpoint(path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with _open_tar(path) as tar:
        tar.extractall(destination)  # noqa: S202
