"""Entry wrapper — boots the proxy before upstream strix initializes.

The `strix` console script (see pyproject.toml `[project.scripts]`) points
at `strixnoapi.wrap:cli_main`. When invoked, we:

    1. Check STRIX_CLI_MODE env. If unset -> fall through to upstream behavior.
    2. Start the subscription-OAuth proxy on 127.0.0.1:<ephemeral>.
    3. Export OPENAI_API_BASE / OPENAI_API_KEY / STRIX_LLM so litellm routes
       through us without any upstream code changes.
    4. Register shutdown hook.
    5. Dispatch to a strixnoapi subcommand (setup/doctor/resume/report/audit)
       if the first argv token matches, else hand off to upstream strix.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from strixnoapi.proxy.launcher import ProxyHandle


SUBCOMMANDS: dict[str, str] = {
    "setup": "strixnoapi.interface.setup_cmd:main",
    "doctor": "strixnoapi.interface.doctor_cmd:main",
    "resume": "strixnoapi.interface.resume_cmd:main",
    "report": "strixnoapi.interface.report_cmd:main",
    "audit": "strixnoapi.interface.audit_cmd:main",
    "update": "strixnoapi.interface.update_cmd:main",
}


def install_proxy() -> "ProxyHandle | None":
    """Boot the proxy if STRIX_CLI_MODE is set. Returns handle or None."""
    cli_mode = os.environ.get("STRIX_CLI_MODE", "").strip().lower()
    if not cli_mode or cli_mode == "api":
        return None

    from strixnoapi.interface.detector import resolve_cli_mode
    from strixnoapi.proxy.launcher import start_proxy

    resolved_mode = resolve_cli_mode(cli_mode)

    audit_dir = Path.home() / ".strix" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    handle = start_proxy(resolved_mode, audit_dir)

    os.environ["OPENAI_API_BASE"] = f"http://127.0.0.1:{handle.port}/v1"
    os.environ["OPENAI_API_KEY"] = handle.token
    os.environ["LLM_API_KEY"] = handle.token
    os.environ.setdefault("STRIX_LLM", f"openai/{_default_model(resolved_mode)}")
    return handle


def _default_model(cli_mode: str) -> str:
    overrides = {
        "claude": os.environ.get("STRIX_CLAUDE_MODEL", "claude-sonnet-4-6"),
        "codex": os.environ.get("STRIX_CODEX_MODEL", "gpt-5.4"),
        "gemini": os.environ.get("STRIX_GEMINI_MODEL", "gemini-2.5-pro"),
        "cursor": os.environ.get("STRIX_CURSOR_MODEL", "auto"),
    }
    return overrides.get(cli_mode, "gpt-5.4")


def _dispatch_subcommand(name: str) -> int:
    entry = SUBCOMMANDS[name]
    module_path, _, func_name = entry.partition(":")
    import importlib

    module = importlib.import_module(module_path)
    func = getattr(module, func_name)
    result = func(sys.argv[2:])
    return 0 if result is None else int(result)


def cli_main() -> int:
    """Console-script entrypoint."""
    if len(sys.argv) >= 2 and sys.argv[1] in SUBCOMMANDS:
        return _dispatch_subcommand(sys.argv[1])

    install_proxy()

    from strix.interface.main import main as upstream_main

    upstream_main()
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
