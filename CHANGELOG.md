# Changelog

All notable changes to strixnoapi are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-04-17

First public preview of strixnoapi — a hardened fork of
[`usestrix/strix`](https://github.com/usestrix/strix) that routes LLM
calls through the user's CLI subscription (Claude Max/Pro, ChatGPT
Plus/Pro, Gemini Advanced, Cursor Pro) via a local OAuth proxy,
replacing billed API access.

### Added

- `strixnoapi/proxy/` — FastAPI OAuth-backed proxy server on
  `127.0.0.1:<ephemeral>` with bearer-token auth, token-bucket rate
  limiting, curated 20+-pattern secret redaction (inbound + outbound),
  prompt-injection heuristics, hash-chained JSONL audit log, size-cap
  input validation.
- `strixnoapi/proxy/translators/` — Claude Code (Anthropic Messages API
  via `anthropic-beta: oauth-2025-04-20` header), OpenAI Codex (ChatGPT
  backend-api with session auth), Google Gemini (generativelanguage via
  OAuth), Cursor (api.cursor.com proxy, experimental).
- `strixnoapi/interface/` — `strix setup`, `strix doctor`,
  `strix resume`, `strix report`, `strix audit verify`, `strix update`,
  `strix version` subcommands.
- `strixnoapi/security/` — docker-run sandbox profile composer
  (cap-drop ALL, read-only root, PID/memory caps, seccomp), egress
  allowlist builder, permission gate (0o600 enforcement), CycloneDX
  SBOM generator.
- `strixnoapi/runtime/windows_docker_npipe.py` — monkeypatch for the
  Docker Python SDK's `NpipeSocket.send()` on Windows so strix's
  container-create request reliably succeeds. Coerces any bytes-like
  payload to `bytes` and chunks writes at 64 KiB to avoid pywin32's
  buffer-length check.
- `strixnoapi/checkpoint/` — zstd-compressed per-phase scan snapshots
  + `strix resume <run-id>` to continue interrupted scans.
- `strixnoapi/report/` — SARIF 2.1.0 emitter + standalone HTML report
  renderer.
- `containers/Dockerfile.hardened`, `containers/seccomp.json`,
  `containers/docker-run-hardened.sh` — optional hardened sandbox layer
  above upstream's Kali-based pentest image.
- CI: matrix (ubuntu-latest, macos-latest, windows-latest) × Python
  3.12 + 3.13 running ruff + pytest + upstream regression. Nightly
  CVE audit workflow (pip-audit + osv-scanner). Manual-dispatch E2E
  workflow against OWASP Juice Shop.
- Docs: `CLAUDE.md` (agent operational playbook), `README.md`,
  `SECURITY.md`, `THREAT_MODEL.md`, `MIGRATION.md`, `NOTICE`,
  `CHANGELOG.md`.

### Changed

- `strix` console-script entrypoint now points at
  `strixnoapi.wrap:cli_main`. The wrap boots the proxy, exports
  `OPENAI_API_BASE` + `OPENAI_API_KEY` before LiteLLM initializes, and
  hands off to `strix.interface.main:main` with zero upstream code
  edits. Upstream's original entrypoint remains reachable as
  `strix-upstream`.
- `pyproject.toml` renamed project to `strixnoapi`, added deps
  (fastapi, uvicorn, httpx, zstandard, questionary), added dev deps
  (respx, pip-audit).

### Fixed

- **Anthropic OAuth content gate (CRITICAL)**: Anthropic's subscription
  OAuth path only accepts the EXACT system prompt
  `"You are Claude Code, Anthropic's official CLI for Claude."`. Any
  deviation returns HTTP 429 with body `{"type":"rate_limit_error"}`
  even at near-zero quota utilization. strixnoapi's `claude_code`
  translator locks `system` to this exact string and folds the
  caller's real system prompt into the first user message wrapped in
  `<strix_system>…</strix_system>` tags.
- **Windows Docker SDK buffer bug (CRITICAL)**: upstream
  `docker.transport.npipesocket` passes unbounded payloads to
  `win32file.WriteFile`, which rejects `memoryview` inputs whose
  length cannot be represented as a signed 32-bit int ("Buffer length
  can be at most -1 characters"). Fixed via runtime monkeypatch in
  `strixnoapi.runtime.windows_docker_npipe` applied from
  `strixnoapi.wrap.cli_main`.
- Strix's `warm_up_llm` short-circuited to a no-op when CLI mode is
  active; the launcher already verifies proxy reachability via
  `/health` during startup, so the second warm-up is redundant and
  contributed to subscription-OAuth flake.

### Security

- Proxy bound to `127.0.0.1` only; UUID bearer token required on every
  request.
- OAuth tokens never persisted to strixnoapi config or logs; read
  fresh from CLI-native credential paths on every request.
- Custom seccomp profile blocks `ptrace`, `keyctl`, `perf_event_open`,
  `bpf`, `reboot`, kernel-module ops.
- Hash-chained audit log with `strix audit verify` tamper detection.

### Known limitations

- Cursor translator is experimental; API schema may drift.
- Anthropic's OAuth path is bound by the Claude Max/Pro subscription's
  5-hour token budget (not a strixnoapi limitation; utilization is
  surfaced in response headers and logged on 429).

[Unreleased]: https://github.com/keeganthewhi/strix-noapi/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/keeganthewhi/strix-noapi/releases/tag/v0.1.0
