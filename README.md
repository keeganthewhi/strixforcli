# strixnoapi

**Autonomous AI pentester, powered by your existing AI CLI subscription.**

A hardened fork of [`usestrix/strix`](https://github.com/usestrix/strix) that routes
LLM calls through **Claude Max/Pro**, **ChatGPT Plus/Pro**, **Gemini Advanced**,
or **Cursor Pro** using the OAuth token from each CLI's native login — no API keys,
no token billing, no surprise costs.

[![upstream](https://img.shields.io/badge/upstream-usestrix%2Fstrix-blue)](https://github.com/usestrix/strix)
[![license](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)
[![python](https://img.shields.io/badge/python-3.12%2B-blue)]()

> **Scope & authorization**: Strix is a pentesting tool. Only scan systems you
> own or have explicit authorization to test. See `SECURITY.md`.

The upstream README is preserved at [`README.upstream.md`](./README.upstream.md).

---

## Why

The upstream Strix agent requires `STRIX_LLM` + `LLM_API_KEY` and bills per
token through the model provider. If you already pay for Claude Max, ChatGPT
Plus, Gemini Advanced, or Cursor Pro, that's money you're leaving on the
table — and for multi-hour pentest runs, the API bill is the dominant cost.

**strixnoapi keeps the upstream scan engine 100% intact** and adds:

1. **Subscription-OAuth proxy** — a local FastAPI server that translates
   LiteLLM-style requests into provider-native API calls authenticated with
   your CLI's OAuth token. Zero changes to Strix's 300-iteration agent loop,
   Jinja prompts, or vulnerability taxonomy.
2. **Security hardening above upstream** — `cap-drop=ALL`, custom seccomp,
   `--read-only` root, PID/memory caps, hash-chained audit log, curated
   secret redaction (inbound + outbound), prompt-injection guard, permission
   gate on config files, CycloneDX SBOM.
3. **UX + reliability upgrades** — interactive `strix setup`, `strix doctor`
   diagnostics, `strix resume` from checkpoint, SARIF + HTML report exports,
   `strix audit verify` tamper-check.

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/YOUR_USER/strixnoapi.git
cd strixnoapi
uv sync
```

### 2. Authenticate one CLI (once)

Any of these works:

| CLI | Install | Log in |
|---|---|---|
| Claude Code | `npm i -g @anthropic-ai/claude-code` | `claude` |
| OpenAI Codex | `npm i -g @openai/codex` | `codex login` |
| Google Gemini | `npm i -g @google/gemini-cli` | `gemini` |
| Cursor | `curl https://cursor.com/install \| bash` | `cursor-agent login` |

### 3. Set up strixnoapi

```bash
uv run strix setup --auto        # detects + writes ~/.strix/cli-config.json (0o600)
uv run strix doctor              # preflight checks
```

### 4. Scan

```bash
# Local target (OWASP Juice Shop is a good demo)
docker run -d --name juice -p 3000:3000 bkimminich/juice-shop

# Full scan
STRIX_CLI_MODE=claude uv run strix \
  --target http://host.docker.internal:3000 \
  --non-interactive \
  --scan-mode standard
```

### 5. Inspect results

```bash
ls strix_runs/<run-id>/                         # upstream deliverables
uv run strix report <run-id> --format sarif     # SARIF 2.1.0 (GitHub-ingestible)
uv run strix report <run-id> --format html      # standalone HTML report
uv run strix audit verify <run-id>              # verify the hash-chained audit log
```

### 6. Resume an interrupted scan

```bash
uv run strix resume <run-id>    # picks up from the last phase checkpoint
```

---

## Architecture

```
Strix agent loop (UNCHANGED from upstream)
       │ litellm.acompletion(...)
       ▼
http://127.0.0.1:<ephemeral>/v1/chat/completions    (FastAPI, bearer-auth, rate-limited)
       │ Validates, redacts, scans for injection, audits
       ▼
One of: claude_code / codex / gemini / cursor translator
       │ Loads OAuth token from ~/.<cli>/ on every call (never cached, never persisted)
       ▼
api.anthropic.com / chatgpt.com / generativelanguage.googleapis.com / api.cursor.com
       │ Billed to your subscription
       ▼
Response streamed back, outbound redaction, audit append
```

See `CLAUDE.md` for the full agent operational playbook and `MIGRATION.md`
for a detailed diff from upstream.

---

## Security posture

strixnoapi inherits every security property from upstream Strix and adds:

- **Proxy bound to 127.0.0.1 only.** UUID bearer token required on every request.
- **Credential files must be 0o600** (Unix). Refuses to start otherwise.
- **OAuth tokens never persisted** to our config or logs. Read per-request from
  CLI-native paths.
- **Hash-chained audit log** — `strix audit verify` detects tampering.
- **Secret redaction** with 20+ curated patterns (AWS, GitHub, JWT, Anthropic,
  OpenAI, Stripe, Slack, private keys, etc.) runs on both the prompt and the
  model's response.
- **Prompt injection guard** — 8 pattern families, strict mode (`STRIX_INJECTION_STRICT=1`)
  returns HTTP 400 instead of just logging.
- **Hardened sandbox image** (`containers/Dockerfile.hardened`) — strips setuid
  bits, removes su/sudo, layered on top of upstream's Kali-based pentest image.
- **Custom seccomp profile** (`containers/seccomp.json`) — denies `ptrace`,
  `keyctl`, `perf_event_open`, `bpf`, kernel module manipulation, `reboot`, etc.
- **`docker-run-hardened.sh`** — applies `cap-drop=ALL`, `no-new-privileges`,
  `--read-only`, PID/memory caps, tmpfs scratch mounts.

See `SECURITY.md` for the threat model and disclosure policy, and
`THREAT_MODEL.md` for the STRIDE analysis.

---

## Supported CLIs (2026 versions)

| CLI | Package | Status | Notes |
|---|---|---|---|
| Claude Code | `@anthropic-ai/claude-code` | Stable | OAuth via `anthropic-beta: oauth-2025-04-20` header |
| OpenAI Codex | `@openai/codex` | Stable | Session-based (chatgpt.com backend-api) |
| Google Gemini | `@google/gemini-cli` | Stable | Google OAuth + generativelanguage.googleapis.com |
| Cursor | `cursor-agent` (curl installer) | **Experimental** | api.cursor.com — schema may drift |

Any CLI you haven't logged into is ignored. `strix setup --auto` picks the
first authenticated one in order: `claude → codex → cursor → gemini`.

---

## Configuration

Override anything via env (see `.env.example` for the full list):

```bash
export STRIX_CLI_MODE=claude              # or: codex, cursor, gemini, auto, api
export STRIX_LOG_PROMPTS=0                # 1 to log redacted prompts (privacy)
export STRIX_PROXY_RATE_LIMIT=30          # requests/min
export STRIX_PROXY_INACTIVITY_S=1800      # upstream call timeout
export STRIX_CLAUDE_MODEL=claude-opus-4-7 # per-CLI model override
export STRIX_ENFORCE_PERMISSIONS=1        # 0 to skip 0o600 checks (not recommended)
```

Config file: `~/.strix/cli-config.json` (written by `strix setup`, mode 0o600).

---

## API-key fallback

If you want to fall back to API-key billing (or run a model strixnoapi doesn't
support):

```bash
unset STRIX_CLI_MODE
export STRIX_LLM=openai/gpt-5.4
export LLM_API_KEY=sk-...
uv run strix --target http://...           # falls through to upstream strix
```

The `strix-upstream` binary is also available as a direct passthrough.

---

## License

Apache 2.0. See `LICENSE`.

Upstream Strix is © 2025 OmniSecure Inc.; see `NOTICE` for attribution.

---

## Contributing

See `CONTRIBUTING.md` (inherited from upstream) and `CLAUDE.md` (agent
operational playbook).

Before submitting:
```bash
uv run ruff check strixnoapi/
uv run pytest tests/
uv run strix audit verify <any-recent-run>   # sanity check
```

---

## Project status

**Preview.** The upstream Strix scan engine is production-grade and ships real
findings. The subscription-OAuth proxy is the newer layer; Claude / Codex /
Gemini have been validated, Cursor is experimental. Expect version churn in the
CLI subscription APIs — run `uv run strix doctor` if something regresses.
