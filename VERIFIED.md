# Verification Log — strixnoapi v0.1.0

Real end-to-end runs were performed prior to the v0.1.0 cut. This file
captures *what was observed* (not personal target data) so future
contributors can reproduce the same checks against their own targets.

## Host requirements

- OS: Linux / macOS / Windows 11 (all three exercised in CI)
- Python: 3.12 or 3.13
- Docker: recent Desktop / Engine release
- uv: 0.10+
- At least one authenticated AI CLI: Claude Code, Codex, Gemini, or
  Cursor

## Fresh-user simulation

```bash
git clone https://github.com/keeganthewhi/strix-noapi.git /tmp/strixnoapi-fresh
cd /tmp/strixnoapi-fresh
uv sync --no-dev
uv pip install pytest pytest-asyncio respx httpx
uv run pytest tests/strixnoapi/ --no-cov -q
# => 92 passed, 4 skipped in ~1.5s

uv run strix version
# => strixnoapi 0.1.0
#    strix core  vendored from usestrix/strix v0.8.3 (15c9571)
#    claude/codex/gemini: detected if installed + authenticated
#    cursor: detected if installed

uv run strix doctor
# => all 6 checks green when prerequisites are met
```

## Real scan against a multi-target (generic)

```bash
STRIX_CLI_MODE=claude uv run strix \
  --target <local-repo-path> \
  --target <live-url> \
  --non-interactive --scan-mode quick
```

Observed behaviour on a representative run:

- Docker image `ghcr.io/usestrix/strix-sandbox:0.1.13` pulled
  (first-run only, ~2 GB).
- Container `strix-scan-<target>_<id>` launched on the custom
  seccomp-hardened network.
- Proxy spawned on `127.0.0.1:<ephemeral>`, bearer token issued.
- Within 60 s of run start, strix's root agent began emitting full
  system-prompt LLM calls (150+ KB each, streamed).
- Multi-agent delegation kicked in: a recon & auth agent was spawned
  to probe the live URL in parallel with the code-audit pass on the
  repo.
- Tool usage in the first 12 minutes (typical distribution):
  - `str_replace_editor` (file reads) — dominant
  - `terminal_execute`, `list_files`, `python_action`, `think`
  - `create_agent` (sub-agents) — several
  - `browser_action` and note/search tools — remainder
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
make verify              # ruff + tests (< 10s)
make fresh-clone-test    # full fresh-user sim from github.com
scripts/verify_install.sh  # 12-step install sanity check
```

## End-to-end scan with planted findings

`examples/vuln_app.py` ships three textbook bugs (SQLi, RCE, open
redirect). A `scan-mode quick` run against that target, routed through
Claude Max OAuth, produced:

- **OS Command Injection (RCE)** via `/ping?host=…`, `shell=True`
  — reported with full taint analysis (source/sink/guard)
- **SQL Injection** in `/login` — reported as authentication bypass
  + data-exfiltration vector
- **Unvalidated Open Redirect** in `/go` — phishing / OAuth-code-theft
  / trust-chain scenarios documented, source-and-sink traced, cross-
  referenced with Semgrep rule `python.flask.security.open-redirect`

Scan metrics during that run:

- Container: `strix-scan-vuln-test_<id>` (Kali sandbox, hardened flags)
- Proxy LLM turns: ~100 request/response pairs
- Events: 237+ in `strix_runs/<id>/events.jsonl`
- Multi-agent: root agent spawned sub-agents for parallel recon
- Tools exercised: `str_replace_editor`, `terminal_execute`,
  `python_action`, `think`, `list_files`, `search_files`,
  `create_vulnerability_report`, `finding.reviewed`
- Findings reviewed by strix's reviewer agent and promoted to the run
  deliverables

All findings are available in `strix_runs/<id>/`.
