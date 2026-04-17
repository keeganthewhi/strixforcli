"""Windows Docker SDK: chunked NpipeSocket.send() fix.

The `docker` Python SDK (>=7.1.0) ships a `NpipeSocket.send()` that calls
`win32file.WriteFile(handle, data, overlapped)` with the full payload at
once. pywin32 rejects `memoryview`/`bytearray` arguments whose implicit
length it cannot represent, surfacing as:

    ValueError: Buffer length can be at most -1 characters

This manifests inside strix's `runtime.create_sandbox()` because the
container-create request body (mounts, env, labels, …) is built up by
`urllib3` and streamed via `http.client.HTTPConnection.send()` which
passes unbounded `bytes`/`memoryview` chunks to the Docker socket.

Two independent issues, both fixed here:

  1. Convert non-`bytes` buffers to `bytes` before handing to WriteFile.
  2. Chunk writes at a safe ceiling (64 KiB) so named-pipe internal
     buffer accounting can't overflow.

Apply once per process; idempotent.
"""

from __future__ import annotations

import os
import sys
from typing import Any


SAFE_CHUNK_BYTES = 64 * 1024

_APPLIED = False


def apply() -> bool:
    """Patch docker.transport.npipesocket.NpipeSocket if on Windows.

    Returns True if the patch was applied this invocation, False if it
    was a no-op (non-Windows, module missing, or already patched).
    """
    global _APPLIED  # noqa: PLW0603
    if _APPLIED:
        return False
    if sys.platform != "win32":
        return False
    if os.environ.get("STRIXNOAPI_SKIP_NPIPE_PATCH") == "1":
        return False

    try:
        from docker.transport import npipesocket  # type: ignore[import-not-found]
    except ImportError:
        return False

    cls = getattr(npipesocket, "NpipeSocket", None)
    if cls is None:
        return False

    original_send = cls.send
    original_sendall = cls.sendall
    cls.send = _make_patched_send(original_send)
    cls.sendall = _make_patched_sendall()

    _APPLIED = True
    return True


def _make_patched_send(original_send: Any) -> Any:
    """Wrap NpipeSocket.send to accept any bytes-like object and chunk it."""

    from docker.transport import npipesocket  # type: ignore[import-not-found]

    import pywintypes  # type: ignore[import-not-found]
    import win32api  # type: ignore[import-not-found]
    import win32event  # type: ignore[import-not-found]
    import win32file  # type: ignore[import-not-found]

    def _write_chunk(sock: Any, chunk: bytes) -> int:
        """Single WriteFile for one bounded chunk; returns bytes written."""
        event = win32event.CreateEvent(None, True, True, None)
        try:
            overlapped = pywintypes.OVERLAPPED()
            overlapped.hEvent = event
            win32file.WriteFile(sock._handle, chunk, overlapped)
            wait_result = win32event.WaitForSingleObject(event, sock._timeout)
            if wait_result == win32event.WAIT_TIMEOUT:
                win32file.CancelIo(sock._handle)
                raise TimeoutError
            return int(win32file.GetOverlappedResult(sock._handle, overlapped, 0))
        finally:
            win32api.CloseHandle(event)

    def patched_send(self: Any, string: Any, flags: int = 0) -> int:  # noqa: ARG001
        if self._closed:
            raise RuntimeError("Can not reuse socket after connection was closed.")
        data = _coerce_bytes(string)
        total = len(data)
        if total == 0:
            return 0
        written = 0
        view = memoryview(data)
        while written < total:
            chunk = bytes(view[written : written + SAFE_CHUNK_BYTES])
            n = _write_chunk(self, chunk)
            if n == 0:
                break
            written += n
        return written

    # Keep a reference so tests can restore via npipesocket._strixnoapi_original_send.
    npipesocket._strixnoapi_original_send = original_send
    return patched_send


def _make_patched_sendall() -> Any:
    def patched_sendall(self: Any, string: Any, flags: int = 0) -> None:
        remaining = _coerce_bytes(string)
        total = len(remaining)
        sent = 0
        while sent < total:
            n = self.send(remaining[sent:], flags)
            if not n:
                raise OSError("NpipeSocket.sendall: underlying send returned 0")
            sent += n
        return None

    return patched_sendall


def _coerce_bytes(obj: Any) -> bytes:
    """Normalize any bytes-like object to a plain bytes instance.

    pywin32 refuses ``memoryview``/``bytearray`` via its buffer-length
    check; ``bytes(mv)`` copies the payload into an immutable buffer
    pywin32 accepts.
    """
    if isinstance(obj, bytes):
        return obj
    if isinstance(obj, (bytearray, memoryview)):
        return bytes(obj)
    if isinstance(obj, str):
        return obj.encode("utf-8")
    return bytes(obj)
