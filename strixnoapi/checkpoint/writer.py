"""Write zstd-compressed checkpoint snapshots for a scan run."""

from __future__ import annotations

import json
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import zstandard as zstd


CHECKPOINT_VERSION = 1


@dataclass(frozen=True)
class CheckpointMeta:
    version: int
    run_id: str
    phase: str
    created_ts: float
    files: list[str]


def write_checkpoint(run_dir: Path, phase: str, source_dirs: list[Path] | None = None) -> Path:
    ck_dir = run_dir / "checkpoints"
    ck_dir.mkdir(parents=True, exist_ok=True)
    out_path = ck_dir / f"phase_{phase}.tar.zst"
    tar_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="strix-ckpt-", suffix=".tar", delete=False
        ) as tmp:
            tar_path = Path(tmp.name)
        with tarfile.open(tar_path, "w") as tar:
            meta = CheckpointMeta(
                version=CHECKPOINT_VERSION,
                run_id=run_dir.name,
                phase=phase,
                created_ts=time.time(),
                files=[],
            )
            for src in source_dirs or [run_dir]:
                if src.exists():
                    tar.add(src, arcname=src.name)
            meta_bytes = json.dumps(asdict(meta)).encode("utf-8")
            info = tarfile.TarInfo(name="CHECKPOINT_META.json")
            info.size = len(meta_bytes)
            import io

            tar.addfile(info, io.BytesIO(meta_bytes))
        cctx = zstd.ZstdCompressor(level=10, threads=-1)
        with tar_path.open("rb") as tar_in, out_path.open("wb") as ck_out:
            cctx.copy_stream(tar_in, ck_out)
        return out_path
    finally:
        if tar_path and tar_path.exists():
            tar_path.unlink(missing_ok=True)
