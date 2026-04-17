"""Proxy runtime settings — populated from env by the spawned server process."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProxySettings:
    port: int
    token: str
    cli_mode: str
    audit_dir: Path
    rate_limit_rpm: int = 30
    inactivity_timeout_s: int = 1800
    log_prompts: bool = False
    bind_host: str = "127.0.0.1"
    max_prompt_bytes: int = 2 * 1024 * 1024
    max_message_bytes: int = 256 * 1024

    @classmethod
    def from_env(cls) -> ProxySettings:
        port = int(os.environ["STRIX_PROXY_PORT"])
        token = os.environ["STRIX_PROXY_TOKEN"]
        cli_mode = os.environ["STRIX_PROXY_CLI_MODE"]
        audit_dir = Path(os.environ["STRIX_PROXY_AUDIT_DIR"])
        return cls(
            port=port,
            token=token,
            cli_mode=cli_mode,
            audit_dir=audit_dir,
            rate_limit_rpm=int(os.environ.get("STRIX_PROXY_RATE_LIMIT", "30")),
            inactivity_timeout_s=int(os.environ.get("STRIX_PROXY_INACTIVITY_S", "1800")),
            log_prompts=os.environ.get("STRIX_LOG_PROMPTS", "0") == "1",
            bind_host="127.0.0.1",
        )
