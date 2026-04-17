# Verification Log — strixnoapi v0.1.0

Real end-to-end run performed on 2026-04-17. This file captures what
was actually observed so future contributors can reproduce.

## Host environment

- OS: Windows 11 Pro (cp1252 console)
- Python: 3.14.3
- Docker: 29.3.1 (Desktop, named-pipe socket)
- uv: 0.10.12
- Claude CLI: 2.x (Claude Max subscription, OAuth authenticated)
- Codex CLI: 0.12x (ChatGPT Plus session)
- Gemini CLI: 0.37x (Google OAuth)
- Cursor CLI: installed, not authenticated (expected — Cursor support
  is experimental)

## Fresh-user simulation

```bash
git clone https://github.com/keeganthewhi/strixnoapi.git /tmp/strixnoapi-fresh
cd /tmp/strixnoapi-fresh
uv sync --no-dev
uv pip install pytest pytest-asyncio respx httpx
uv run pytest tests/strixnoapi/ --no-cov -q
# => 92 passed, 4 skipped in 1.56s

uv run strix version
# => strixnoapi 0.1.0
#    strix core  vendored from usestrix/strix v0.8.3 (15c9571)
#    python      3.14.3 (win32)
#    claude/codex/gemini: installed + authenticated
#    cursor: installed

uv run strix doctor
# => all 6 checks green

uv run python -c "<spawn proxy, real Claude OAuth call, pong response>"
# => proxy up :54703 / OK: pong
```

## Real scan against multi-target

```bash
STRIX_CLI_MODE=claude uv run strix \
  --target /d/Projects/ayarticaret \
  --target https://3yoto.com \
  --non-interactive --scan-mode quick
```

Observed behaviour:

- Docker image `ghcr.io/usestrix/strix-sandbox:0.1.13` pulled
  (first-run only, ~2 GB).
- Container `strix-scan-ayarticaret_<id>` launched on the custom
  seccomp-hardened network.
- Proxy spawned on `127.0.0.1:<ephemeral>`, bearer token issued.
- Within 60 s of run start, strix's root agent began emitting full
  system-prompt LLM calls (150+ KB each, streamed).
- Multi-agent delegation kicked in: a `Recon & Auth Agent` was spawned
  to probe the live URL in parallel with the code-audit pass on the
  repo.
- Tool usage in the first 12 minutes:
  - `str_replace_editor` (file reads) — 78
  - `terminal_execute` — 58
  - `list_files` — 40
  - `python_action` — 37
  - `think` — 26
  - `create_agent` (sub-agents) — 8
  - `browser_action` — 6
  - `search_files`, `create_note`, `wait_for_message`, etc. — remaining
- Proxy handled every LLM turn: 300+ request/response pairs logged in
  `~/.strix/audit/proxy-<pid>.jsonl`, hash chain intact.
- No `rate_limit_error` 429s after the content-gate fix landed.
- No `Buffer length` errors after the Windows Docker SDK patch landed.

## Tests, lint, CI

```
uv run pytest tests/strixnoapi/ --no-cov
# => 92 passed, 4 skipped (Windows-only perm tests skipped on Windows)

uv run pytest tests/ --ignore=tests/strixnoapi --ignore=tests/runtime --no-cov
# => 109 passed (upstream regression tests)

uv run ruff check strixnoapi/
# => All checks passed!
```

CI matrix (ubuntu-latest, macos-latest, windows-latest) × (py3.12,
py3.13) green on every commit from `77c5135` onward.

## What a fresh user gets

1. `uv sync` → full dependency graph.
2. `uv run strix setup --auto` → writes
   `~/.strix/cli-config.json` at mode 0o600 with whichever of
   claude/codex/gemini/cursor they've authenticated.
3. `uv run strix doctor` → green.
4. `STRIX_CLI_MODE=<mode> uv run strix --target …` → full pentest
   through their subscription quota, no API key required.
5. `uv run strix audit verify <run-id>` → tamper check on the hash
   chain.
6. `uv run strix report <run-id> --format sarif` → SARIF 2.1.0 report.
7. `uv run strix resume <run-id>` → continue if interrupted.

## Limits we know about

- Anthropic's subscription OAuth is capped by Claude Max/Pro's own
  5-hour budget — strixnoapi logs utilization from response headers.
- Cursor translator is experimental until someone exercises the full
  path end-to-end on their Cursor Pro subscription.
- `docker.transport.npipesocket` patch is conservative (64 KiB
  chunks); if a future strix release sends > 1 GB request bodies the
  chunk loop is still correct but the time spent in WriteFile grows
  linearly.

## Reproducibility

Re-run this verification on any target at any time:

```bash
make verify            # ruff + tests (< 10s)
make fresh-clone-test  # full fresh-user sim from github.com
```
