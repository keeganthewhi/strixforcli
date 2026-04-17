# strixnoapi — Claude Agent Playbook

> Operational playbook for Claude Code (and any agent) working inside this
> repository. Read first, every session. Sits on top of the global
> `~/.claude/CLAUDE.md` — anything here overrides for this project.

---

## What this project is

**strixnoapi** is a hardened fork of [`usestrix/strix`](https://github.com/usestrix/strix) —
a production-grade autonomous AI pentesting agent — that removes the API-key
requirement. Users point it at their **Claude Max/Pro**, **ChatGPT Plus/Pro**,
**Gemini Advanced**, or **Cursor Pro** subscription and the full Strix scan
engine runs through that subscription's OAuth token.

Three goals, in strict order:

1. **Keep Strix's scan engine intact.** We do NOT rewrite the 300-iteration
   agent loop, multi-agent delegation, Jinja prompts, XML tool-call parser,
   skills system, vulnerability taxonomy, or deliverable reports.
2. **Harden above upstream.** Stricter sandbox flags, hash-chained audit log,
   secret redaction both directions, prompt-injection guard, SBOM, permission
   gates, curated secret patterns.
3. **Ship UX on top.** `strix setup`, `strix doctor`, `strix resume`,
   SARIF/HTML/PDF reports, cross-OS test matrix.

**Upstream code under `strix/` is untouched.** `strixnoapi/` is additive.
Security patches from upstream remain cherry-pickable via the `upstream` remote.

---

## Quick reference

```bash
# One-time — user authenticates whichever CLI they already pay for
claude                          # browser OAuth
# OR: codex login, cursor-agent login, gemini

# Install + setup
uv sync
uv run strix setup --auto       # detects + writes ~/.strix/cli-config.json
uv run strix doctor             # preflight diagnostics

# Scan
STRIX_CLI_MODE=claude uv run strix --target http://host.docker.internal:3000 -n

# Inspect
uv run strix audit verify <run-id>
uv run strix report <run-id> --format sarif > report.sarif
uv run strix resume <run-id>    # continue from last checkpoint
```

---

## Architecture (how it actually works)

```
Strix agent loop (UNCHANGED)
        │ litellm.acompletion(model="claude-sonnet-4-6", …)
        ▼
127.0.0.1:<port>/v1/chat/completions    ← our local FastAPI proxy
        │ bearer-auth, rate-limit, scrubadub, injection guard, audit
        ▼
strixnoapi.proxy.translators.<cli>      ← read ~/.<cli>/ OAuth token
        │ httpx.AsyncClient
        ▼
api.anthropic.com / chatgpt.com / generativelanguage.googleapis.com / api.cursor.com
        │ billed against user's subscription quota
        ▼
response streamed back, scrubadub redacts outbound
```

Key insight: `strixnoapi/wrap.py` is the `strix` console-script entrypoint.
It boots the proxy, sets `OPENAI_API_BASE` + `OPENAI_API_KEY` + `STRIX_LLM`,
then invokes upstream `strix.interface.main:main`. Upstream never knows our
proxy exists — it just sees an OpenAI-compatible endpoint.

---

## Repository map

```
D:\Projects\strixnoapi\
├── strix/                            # UNCHANGED upstream
├── strixnoapi/
│   ├── wrap.py                       # Entry hook — boots proxy, hands off
│   ├── proxy/
│   │   ├── server.py                 # FastAPI app (OpenAI + Anthropic APIs)
│   │   ├── launcher.py               # Ephemeral port, child process, atexit
│   │   ├── auth.py                   # Bearer-token middleware
│   │   ├── ratelimit.py              # Token bucket
│   │   ├── audit.py                  # Hash-chained JSONL logger
│   │   ├── validation.py             # Prompt size, role whitelist, unicode
│   │   ├── injection_guard.py        # Prompt-injection heuristics
│   │   ├── redaction.py              # Secret-pattern redactor
│   │   ├── credentials.py            # Read ~/.<cli>/ OAuth files
│   │   └── translators/              # One per CLI
│   │       ├── base.py               # Abstract BaseTranslator
│   │       ├── claude_code.py        # Anthropic Messages API + OAuth beta
│   │       ├── codex.py              # chatgpt.com backend-api + session token
│   │       ├── gemini.py             # Google generativelanguage + OAuth
│   │       └── cursor.py             # api.cursor.com (experimental)
│   ├── interface/                    # Subcommands
│   │   ├── setup_cmd.py              # strix setup
│   │   ├── doctor_cmd.py             # strix doctor
│   │   ├── resume_cmd.py             # strix resume
│   │   ├── report_cmd.py             # strix report
│   │   ├── audit_cmd.py              # strix audit verify
│   │   ├── update_cmd.py             # strix update (cherry-pick upstream)
│   │   └── detector.py               # CLI binary + OAuth detection
│   ├── security/
│   │   ├── sandbox_profile.py        # docker-run flag composer
│   │   ├── egress_allowlist.py       # per-scan iptables
│   │   ├── secret_patterns.py        # re-export of redaction patterns
│   │   ├── permission_gate.py        # 0o600 enforcement
│   │   └── sbom.py                   # CycloneDX generator
│   ├── checkpoint/
│   │   ├── writer.py                 # zstd per-phase snapshots
│   │   └── reader.py                 # restore from snapshot
│   └── report/
│       ├── sarif.py                  # SARIF 2.1.0 emitter
│       └── html.py                   # Standalone HTML report
├── containers/
│   ├── Dockerfile                    # UNCHANGED upstream sandbox
│   ├── Dockerfile.hardened           # Optional hardened overlay
│   ├── seccomp.json                  # Custom seccomp profile
│   └── docker-run-hardened.sh        # Wrapper applying hardened flags
├── tests/
│   ├── strixnoapi/                   # Our tests (>80 unit + integration)
│   └── <upstream dirs>/              # Unchanged upstream tests
├── pyproject.toml                    # Renamed, strix + strixnoapi packaged
├── NOTICE                            # Apache 2.0 upstream attribution
├── README.md                         # User quickstart
├── SECURITY.md                       # Threat model + disclosure
├── MIGRATION.md                      # Diff vs upstream
├── THREAT_MODEL.md                   # STRIDE-ish analysis
└── CLAUDE.md                         # This file
```

---

## Setup flow — what to do when a user says "scan my app"

### Step 1 — Prerequisites

```bash
docker info                   # daemon must be running
uv --version                  # >= 0.10
python --version              # >= 3.12
```

### Step 2 — At least one authenticated CLI

Check the user's system:

```bash
uv run strix doctor
```

If no authenticated CLI, help them install + log in to one:

| CLI | Install | Authenticate |
|---|---|---|
| **Claude Code** | `npm i -g @anthropic-ai/claude-code` | `claude` (browser OAuth) |
| **Codex** | `npm i -g @openai/codex` | `codex login` |
| **Gemini** | `npm i -g @google/gemini-cli` | `gemini` (first run) |
| **Cursor** | `curl https://cursor.com/install \| bash` | `cursor-agent login` |

### Step 3 — Setup

```bash
uv run strix setup --auto
```

Writes `~/.strix/cli-config.json` at mode `0o600`. Detects all 4 CLIs,
picks the first authenticated in order `claude → codex → cursor → gemini`.

### Step 4 — Run the scan

```bash
STRIX_CLI_MODE=<claude|codex|cursor|gemini|auto> \
  uv run strix --target <url-or-repo-or-path> [-n] [-m quick|standard|deep]
```

Targets:
- `--target https://app.com` (live URL)
- `--target ./path/to/repo` (local code, white-box)
- `--target https://github.com/user/repo` (clone + scan)
- `--target 192.168.1.10` (IP, black-box)
- Multiple `--target` flags = multi-target whitebox+live

### Step 5 — Report

```bash
ls strix_runs/<run-id>/                        # upstream's deliverables
uv run strix report <run-id> --format sarif    # our SARIF
uv run strix report <run-id> --format html     # standalone HTML
uv run strix audit verify <run-id>             # tamper check
```

---

## Critical invariants (never violate)

Extends the global `~/.claude/CLAUDE.md` + upstream. In order of importance:

1. **Never persist API keys or OAuth tokens to disk.** OAuth tokens are
   read fresh from `~/.claude/`, `~/.codex/`, `~/.gemini/`, `~/.cursor/`
   on every request. Never copied into `~/.strix/cli-config.json` or
   our audit log.
2. **Credential file perms 0o600 on Unix.** `STRIX_ENFORCE_PERMISSIONS=1`
   by default. Refuse to start if loose perms. Loud error, not silent.
3. **Proxy binds 127.0.0.1 only.** `bind_host="127.0.0.1"` hard-coded.
   Never `0.0.0.0`. UUID bearer token required on every request.
4. **Prompt size cap** 2 MiB total, 256 KiB per message. Reject at proxy
   with HTTP 413.
5. **Secret redaction runs twice** — inbound (prompts may leak secrets
   from scanned code) AND outbound (model may echo secrets). Both logged
   as `pii_kinds` in audit entry.
6. **Hash-chained audit log** — `~/.strix/audit/proxy-<pid>.jsonl`. Each
   entry includes prev-entry SHA-256. `strix audit verify` rejects any
   tampered log.
7. **No prompt content logged** unless `STRIX_LOG_PROMPTS=1` (privacy default).
   Prompt gets redacted before log entry if logging enabled.
8. **Sandbox hardening flags mandatory** when launching pentest container:
   `cap-drop=ALL`, `--security-opt=no-new-privileges`, `--read-only`,
   `--pids-limit=512`, `--memory=4g`, `--security-opt=seccomp=...json`.
9. **Read-only target repo mount** (`/target:ro`). Writable `/workspace:rw`
   only. Docker socket NEVER mounted inside scan sandbox.
10. **No upstream scan logic modified.** If you feel tempted to change
    anything under `strix/`, stop. Write a wrapper instead in `strixnoapi/`.
11. **Upstream tests must still pass.** Run `uv run pytest tests/` before
    committing. Upstream tests live under `tests/agents/`, `tests/llm/`, etc.
12. **Conventional Commits** for commit messages. Every commit pushes to
    `main`. Never force-push. Never `git reset --hard` without explicit ask.

---

## Security hardening (what we do beyond upstream)

| Area | Upstream | strixnoapi |
|------|----------|------------|
| Sandbox capabilities | Default (NET_RAW implied) | `cap-drop=ALL`, opt-in NET_RAW via env |
| Sandbox filesystem | Writable root | `--read-only` root + tmpfs for `/tmp`, `/workspace/.cache` |
| Seccomp | Docker default | Custom profile; denies ptrace, keyctl, perf_event_open, bpf, reboot |
| Resource limits | Unset | `--pids-limit=512`, `--memory=4g`, `--memory-swap=4g` |
| No-new-privs | Unset | Enforced |
| Credential policy | Users set env vars | OAuth token read per-request, never persisted |
| Audit log | Text logs | Hash-chained JSONL, `strix audit verify` detects tampering |
| Secret redaction | `scrubadub` outbound | `scrubadub` + curated 20+ patterns, inbound + outbound |
| Prompt injection | — | 8-pattern heuristic guard, `STRIX_INJECTION_STRICT=1` blocks |
| Permission gate | — | `0o600` on `~/.strix/cli-config.json`, refuse to start if loose |
| SBOM | — | CycloneDX generator (`python -m strixnoapi.security.sbom`) |

---

## Testing

Fast unit + integration tests live under `tests/strixnoapi/`. Upstream
tests live under `tests/agents/`, `tests/llm/`, etc. — both MUST pass.

```bash
uv run pytest tests/                       # full suite
uv run pytest tests/strixnoapi/            # strixnoapi only
uv run pytest tests/strixnoapi/ -v --no-cov  # faster, verbose
STRIX_E2E=1 uv run pytest tests/e2e/       # gated real-CLI tests
```

Test fixtures (`tests/strixnoapi/conftest.py`):
- `tmp_home` — isolates `Path.home()` per test.
- `claude_creds`, `codex_creds`, `gemini_creds`, `cursor_creds` — canned OAuth files at 0o600.

Never commit real credentials. Never mock `load_oauth()` to return real tokens.

---

## Quality gate

Before every commit:

```bash
uv run ruff check strixnoapi/
uv run mypy strixnoapi/        # optional; may have upstream false positives
uv run pytest tests/strixnoapi/ --no-cov
```

All must exit 0. If ruff is stuck on a pattern that's legitimate for our
use case (lazy imports in CLI tools, long URLs in secret patterns), add
a per-file-ignore in `pyproject.toml` — don't sprinkle `noqa` comments.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `No authenticated CLI detected` | No CLI logged in | Run `claude` / `codex login` / `cursor-agent login` / `gemini` |
| `Insecure permissions` on startup | `chmod 644` leak | `chmod 600 ~/.strix/cli-config.json` + any `~/.<cli>/` cred file |
| `Claude OAuth token rejected (401)` | Token expired | `claude` (re-auth in browser) |
| `Codex session rejected` | Session rotated | `codex login` again |
| Proxy port collision | Port in use | Unset `STRIX_PROXY_PORT`, retry |
| Docker not reachable | Daemon down | Start Docker Desktop / systemctl start docker |
| Scan hangs after N minutes | Inactivity watchdog (30 min) | Check target is reachable; `STRIX_PROXY_INACTIVITY_S=3600` to extend |
| Audit verify fails | Log tampered or crash mid-write | Re-run scan; keep prior log for forensics |
| Upstream tests fail after edit | You changed `strix/` accidentally | `git diff strix/` and revert |
| `ruff check` error you can't fix | Legit pattern | Add per-file-ignore in pyproject.toml |

---

## Debugging playbook

### Proxy won't start
```bash
# Run the proxy manually to see startup errors
STRIX_PROXY_PORT=0 STRIX_PROXY_TOKEN=debug STRIX_PROXY_CLI_MODE=claude \
  STRIX_PROXY_AUDIT_DIR=/tmp/audit \
  uv run python -m strixnoapi.proxy.server
```

### LLM call failing
```bash
# Enable prompt logging (redacted)
export STRIX_LOG_PROMPTS=1
# Tail the audit log
tail -f ~/.strix/audit/proxy-*.jsonl | jq .
```

### Sandbox denies a syscall
Check seccomp log:
```bash
docker logs <container>          # EPERM may come from our seccomp.json
# If a tool genuinely needs a blocked syscall, edit containers/seccomp.json
```

### OAuth refresh loop
Claude / Codex tokens rotate ~1h. If the proxy sees 401s repeatedly:
```bash
# Force re-auth on host, then retry
claude                    # or: codex login
```

---

## Git workflow

- `origin`: user-provided remote (add with `git remote add origin <url>`)
- `upstream`: `https://github.com/usestrix/strix.git` — for cherry-picking patches
- Branch: `main` (single-dev). Never force-push. Never delete without explicit ask.
- Commits: Conventional Commits format, ending with `Co-Authored-By: …` trailer.
- Push after every commit.
- On pre-commit hook fail: fix root cause, new commit. Never `--amend` on pushed commits.

Pulling upstream security patches:
```bash
uv run strix update --dry-run            # list pending upstream commits
git merge upstream/main                  # apply after review
uv run pytest                            # ensure nothing broke
```

---

## Autonomous decisions baked into this repo

See `plans/go-check-d-projects-shannonforcli-repo-atomic-pnueli.md` and the
top-of-README summary. Highlights:

- Chosen approach: **Subscription-OAuth HTTP proxy** (not mode-D delegation).
- Proxy bound 127.0.0.1 only, UUID bearer token; no external network exposure.
- Sandbox hardening is **additive** on top of upstream — use the
  `containers/docker-run-hardened.sh` wrapper when launching manually.
- Cursor adapter flagged experimental until first real scan validates it.
- Telemetry OFF by default (`STRIX_TELEMETRY=0`).
- Python 3.12+ only.
- `uv` is the package manager of record.

---

## Contacts

- Upstream: https://github.com/usestrix/strix (report security issues there)
- strixnoapi: open an issue on this fork
- SECURITY.md for disclosure policy
