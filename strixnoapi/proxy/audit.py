"""Hash-chained JSONL audit logger.

Each entry includes `prev_hash` and its own `hash` = SHA-256(prev_hash || canonical-body).
`strix audit verify <run-id>` recomputes the chain and rejects tampering.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType
from typing import Any


GENESIS_HASH = "0" * 64


class AuditLogger(AbstractContextManager["AuditLogger"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._prev_hash = self._load_last_hash()
        self._file = self.path.open("a", encoding="utf-8")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if not self._file.closed:
                self._file.flush()
                self._file.close()

    def append(self, entry: dict[str, Any]) -> str:
        with self._lock:
            payload = dict(entry)
            payload["ts"] = payload.get("ts") or time.time()
            payload["prev_hash"] = self._prev_hash
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256((self._prev_hash + "|" + canonical).encode("utf-8")).hexdigest()
            payload["hash"] = digest
            self._file.write(json.dumps(payload, separators=(",", ":")) + "\n")
            self._file.flush()
            os.fsync(self._file.fileno())
            self._prev_hash = digest
            return digest

    def _load_last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return GENESIS_HASH
        last: str | None = None
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        if not last:
            return GENESIS_HASH
        try:
            entry = json.loads(last)
        except json.JSONDecodeError:
            return GENESIS_HASH
        h = entry.get("hash")
        return h if isinstance(h, str) and len(h) == 64 else GENESIS_HASH


def verify_chain(path: Path) -> tuple[bool, int, str | None]:
    """Return (ok, entries_checked, first_bad_line_reason_or_None)."""
    if not path.exists():
        return False, 0, "audit log does not exist"
    prev = GENESIS_HASH
    n = 0
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            n += 1
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as e:
                return False, n, f"line {lineno}: invalid JSON: {e}"
            if entry.get("prev_hash") != prev:
                return False, n, f"line {lineno}: prev_hash mismatch"
            stored = entry.pop("hash", None)
            canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256((prev + "|" + canonical).encode("utf-8")).hexdigest()
            if digest != stored:
                return False, n, f"line {lineno}: hash mismatch (stored={stored}, computed={digest})"
            prev = digest
    return True, n, None
