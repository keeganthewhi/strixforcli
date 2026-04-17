"""Spawns the proxy as a child process bound to 127.0.0.1 on an ephemeral port."""

from __future__ import annotations

import atexit
import logging
import os
import secrets
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.request import Request, urlopen


if TYPE_CHECKING:
    from pathlib import Path


log = logging.getLogger(__name__)


@dataclass
class ProxyHandle:
    proc: subprocess.Popen
    port: int
    token: str
    cli_mode: str

    def is_alive(self) -> bool:
        return self.proc.poll() is None

    def terminate(self) -> None:
        _terminate(self)


def _pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_healthy(port: int, token: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        try:
            req = Request(url, headers={"Authorization": f"Bearer {token}"})
            with urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.15)
    raise RuntimeError(f"proxy did not become healthy within {timeout}s: {last_err}")


def start_proxy(cli_mode: str, audit_dir: Path, rate_limit_rpm: int = 30) -> ProxyHandle:
    env_port = os.environ.get("STRIX_PROXY_PORT")
    port = int(env_port) if env_port and env_port.isdigit() else _pick_port()
    token = secrets.token_urlsafe(32)

    child_env = os.environ.copy()
    child_env.update(
        {
            "STRIX_PROXY_PORT": str(port),
            "STRIX_PROXY_TOKEN": token,
            "STRIX_PROXY_CLI_MODE": cli_mode,
            "STRIX_PROXY_AUDIT_DIR": str(audit_dir),
            "STRIX_PROXY_RATE_LIMIT": str(rate_limit_rpm),
        }
    )

    kwargs: dict = {
        "env": child_env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        [sys.executable, "-m", "strixnoapi.proxy.server"],
        **kwargs,
    )

    try:
        _wait_healthy(port, token)
    except Exception:
        _terminate_process(proc)
        raise

    handle = ProxyHandle(proc=proc, port=port, token=token, cli_mode=cli_mode)
    atexit.register(_terminate, handle)
    return handle


def _terminate(handle: ProxyHandle) -> None:
    _terminate_process(handle.proc)


def _terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            log.warning("proxy subprocess did not exit after SIGKILL")
    except Exception:  # noqa: BLE001
        pass
