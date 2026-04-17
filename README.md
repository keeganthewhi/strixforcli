# strix-noapi

**Same [Strix](https://github.com/usestrix/strix). No API key. Powered by your AI CLI subscription.**

A hardened fork of [`usestrix/strix`](https://github.com/usestrix/strix) that
replaces the `LLM_API_KEY` requirement with a local OAuth proxy: strix calls
flow through **Claude Max/Pro**, **ChatGPT Plus/Pro**, **Gemini Advanced**,
or **Cursor Pro** subscriptions. Scan engine, prompts, tools, multi-agent
loop, reports — all untouched. Just zero marginal cost per scan.

[![CI](https://github.com/keeganthewhi/strix-noapi/actions/workflows/ci.yml/badge.svg)](https://github.com/keeganthewhi/strix-noapi/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-102%20passing-brightgreen)]()
[![upstream](https://img.shields.io/badge/upstream-usestrix%2Fstrix%20v0.8.3-blue)](https://github.com/usestrix/strix)
[![license](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)
[![python](https://img.shields.io/badge/python-3.12%2B-blue)]()

> **Scope & authorization**: Strix is a pentesting tool. Only scan systems you
> own or have explicit authorization to test. See `SECURITY.md`.

---

## What this is

**If you already know Strix:** this is Strix. Same 300-iteration agent loop,
same Jinja prompts, same skills system, same Docker sandbox with nmap /
subfinder / Semgrep / Playwright / Caido, same `create_vulnerability_report`
tool, same SARIF-compatible output. The upstream `strix/` tree is vendored
verbatim — upstream security patches cherry-pick cleanly with `strix update`.

**What changed:** an additive `strixnoapi/` subpackage that:

1. Runs a local **OAuth proxy** on `127.0.0.1:<ephemeral>` bound with a
   bearer token. Strix's `litellm.acompletion()` hits it via
   `OPENAI_API_BASE`; the proxy reads your CLI's OAuth credentials and
   forwards to the real provider API.
2. Adds a **hardening layer** on top of upstream's sandbox (cap-drop ALL,
   custom seccomp, `--read-only` root, PID/memory caps, hash-chained audit
   log, 20+-pattern secret redaction, prompt-injection guard).
3. Ships **UX commands** strix doesn't have: `strix setup`, `strix doctor`,
   `strix resume`, `strix audit verify`, `strix report --format sarif|html`,
   `strix version`, `strix update`.

The console-script `strix` still runs a full penetration test the same way
it always did — you just don't pay for API tokens.

---

## 60-second quickstart

```bash
git clone https://github.com/keeganthewhi/strix-noapi.git
cd strix-noapi
uv sync
uv run strix setup --auto        # detects + persists chosen CLI
uv run strix doctor              # preflight (all green)
STRIX_CLI_MODE=claude uv run strix \
  --target /path/to/repo --target https://app.example.com \
  --non-interactive --scan-mode deep
```

Authenticate whichever CLI you'll route through — once:

| CLI | Install | Log in |
|---|---|---|
| Claude Code | `npm i -g @anthropic-ai/claude-code` | `claude` |
| OpenAI Codex | `npm i -g @openai/codex` | `codex login` |
| Google Gemini | `npm i -g @google/gemini-cli` | `gemini` |
| Cursor | `curl https://cursor.com/install \| bash` | `cursor-agent login` |

---

## Architecture

```
Strix agent loop (UNCHANGED from upstream)
       │ litellm.acompletion(...)
       ▼
http://127.0.0.1:<ephemeral>/v1/chat/completions
       │ FastAPI proxy: bearer-auth, rate-limit, redact, audit, inject-guard
       ▼
claude_code / codex / gemini / cursor translator
       │ reads OAuth token from ~/.<cli>/ — never persisted
       ▼
api.anthropic.com / chatgpt.com / generativelanguage.googleapis.com / api.cursor.com
       │ billed to YOUR subscription, not an API key
       ▼
Response streamed back, outbound redaction, audit appended
```

---

## Compatibility issues handled automatically

Found and fixed during end-to-end verification against real subscriptions
— users never have to deal with these:

- **Anthropic OAuth content gate** — subscription path only accepts the
  exact Claude Code system prompt. Translator folds strix's real system
  into the first user message wrapped in `<strix_system>…</strix_system>`.
- **Windows Docker SDK npipe buffer bug** — `win32file.WriteFile` refuses
  `memoryview` payloads; runtime patch chunks writes at 64 KiB and coerces
  to `bytes` (idempotent, no-op on non-Windows).
- **strix warm-up double-probe** — monkeypatched to no-op since the
  proxy launcher already verifies `/health`, avoiding wasted subscription
  burst slots.
- **LiteLLM timeout on long turns** — expanded the Anthropic SSE event
  translator to cover `message_start` / `content_block_start` /
  `input_json_delta` / `thinking_delta` / `content_block_stop` /
  `message_stop` / `error` / `ping`, eliminating mid-turn silence.
- **Prompt caching** — `cache_control: {"type":"ephemeral"}` attached to
  the strix_system block so Anthropic's prompt-cache discounts kick in
  (roughly 10× token reduction on sustained runs).

---

## Security posture (delta from upstream)

- Proxy bound to `127.0.0.1` only; UUID bearer token required on every
  request.
- OAuth tokens never persisted to disk by strixnoapi. Read fresh from
  CLI-native paths on every request.
- Hash-chained JSONL audit log (`~/.strix/audit/proxy-<pid>.jsonl`) —
  `strix audit verify` detects any post-hoc tampering.
- 20+-pattern secret redaction (AWS, GitHub, JWT, Anthropic, OpenAI,
  Stripe, Slack, private keys, etc.) runs on BOTH prompt and response.
- Prompt-injection guard — 8 pattern families; strict mode returns 400.
- Sandbox overlay (`containers/Dockerfile.hardened`,
  `containers/seccomp.json`, `containers/docker-run-hardened.sh`):
  `cap-drop=ALL`, `no-new-privileges`, `--read-only`, `--pids-limit=512`,
  `--memory=4g`, custom seccomp denying `ptrace`, `keyctl`,
  `perf_event_open`, `bpf`, kernel-module ops, `reboot`.
- Permission gate refuses to start if `~/.strix/cli-config.json` is
  readable by anyone but the owner (POSIX).
- CycloneDX SBOM on every build.

See `SECURITY.md` and `THREAT_MODEL.md` for the full analysis.

---

## CLI subcommands

| Command | What it does |
|---|---|
| `strix` (default) | Runs a scan — same flags as upstream (`--target`, `--scan-mode`, `--non-interactive`, `--instruction`, `--scope-mode`, `--diff-base`, `--config`) |
| `strix setup [--auto \| --cli <mode>]` | Detect installed CLIs, persist chosen mode, write `~/.strix/cli-config.json` at 0o600 |
| `strix doctor [--json]` | Preflight diagnostics — Python, Docker, port, CLI auth, config perms, disk |
| `strix resume <run-id>` | Continue an interrupted scan from the last checkpoint |
| `strix report <run-id> --format sarif\|html\|markdown` | Export findings |
| `strix audit verify <run-id \| path>` | Recompute and check the hash chain |
| `strix update [--dry-run]` | Pull upstream `usestrix/strix` security patches |
| `strix version` | Print strix-noapi + vendored strix + environment info |
| `strix-upstream` | Original upstream entrypoint, bypasses the proxy |

---

## Configuration reference

```bash
# Required to activate the proxy (otherwise falls through to API-key mode):
export STRIX_CLI_MODE=claude         # or: codex, gemini, cursor, auto

# Optional per-CLI model overrides:
export STRIX_CLAUDE_MODEL=claude-sonnet-4-6
export STRIX_CODEX_MODEL=gpt-5.4
export STRIX_GEMINI_MODEL=gemini-2.5-pro

# Optional proxy tuning:
export STRIX_PROXY_RATE_LIMIT=30     # requests/min (default 30)
export STRIX_PROXY_INACTIVITY_S=1800 # upstream call timeout
export STRIX_LOG_PROMPTS=0           # 1 to log redacted prompts (privacy default: off)
export STRIX_ENFORCE_PERMISSIONS=1   # 0 to skip 0o600 checks (not recommended)

# Optional sandbox control:
export STRIX_ALLOW_NET_RAW=1         # 0 to drop NET_RAW + NET_ADMIN (some nmap modes break)
export STRIXNOAPI_SKIP_NPIPE_PATCH=0 # 1 to skip Windows docker patch
```

Config file (populated by `strix setup`): `~/.strix/cli-config.json` at
mode 0o600.

---

## Fall back to API-key mode (upstream behavior)

```bash
unset STRIX_CLI_MODE
export STRIX_LLM=openai/gpt-5.4
export LLM_API_KEY=sk-...
uv run strix --target …        # or: uv run strix-upstream --target …
```

---

## Tests + lint + CI

```bash
make verify               # ruff + 102 pytest on strixnoapi/
make fresh-clone-test     # simulate a net-new user clone + install + verify
scripts/verify_install.sh # 12-step deep sanity check
```

CI matrix: ubuntu + macos + windows × Python 3.12 + 3.13; runs on every
push to `main`, nightly CVE audit (`pip-audit` + `osv-scanner`), gated
E2E workflow against OWASP Juice Shop.

---

## Docs

| File | What |
|---|---|
| `CLAUDE.md` | Operational playbook for Claude Code + other agents working in the repo |
| `SECURITY.md` | Threat model + disclosure |
| `THREAT_MODEL.md` | STRIDE-ish analysis with trust-boundary diagram |
| `MIGRATION.md` | Per-file diff vs upstream |
| `CHANGELOG.md` | Keep-a-Changelog format, per-release notes |
| `VERIFIED.md` | Real end-to-end run log |
| `CONTRIBUTING.md` | PR checklist + golden rule ("never modify `strix/`") |
| `NOTICE` | Apache 2.0 upstream attribution |

---

## License

Apache 2.0 (inherited from upstream). See `LICENSE`.

Upstream Strix is © OmniSecure Inc.; `NOTICE` carries full attribution.

---

## Project status

**Preview (v0.1.0).** The upstream scan engine is production-grade
(24k★, active maintenance). The subscription-OAuth proxy is the newer
layer — Claude / Codex / Gemini validated end-to-end against real
scans; Cursor translator is experimental until first user exercises
it against a Cursor Pro subscription.

Open an issue on `keeganthewhi/strix-noapi` for bugs in the proxy,
hardening layer, or subcommands. For scan-engine behaviour, upstream
(`usestrix/strix`) is authoritative.
