# Migration — strixnoapi diff from upstream strix

`strixnoapi` is a minimally invasive fork. The scan engine is untouched.
Everything is additive unless noted.

Upstream baseline: `usestrix/strix@15c9571` (v0.8.3, 2026-04).

---

## Tree-level additions

```
strixnoapi/               NEW — our subpackage
  wrap.py                 boots proxy, hands off to upstream main()
  proxy/                  FastAPI OAuth proxy + translators
  interface/              strix setup/doctor/resume/report/audit/update
  security/               sandbox_profile, permission_gate, secret_patterns, SBOM, egress
  checkpoint/             zstd per-phase snapshots for resume
  report/                 SARIF 2.1.0 + HTML emitters

containers/
  Dockerfile              UNCHANGED from upstream
  Dockerfile.hardened     NEW — hardened overlay on top of upstream sandbox
  seccomp.json            NEW — custom seccomp profile
  docker-run-hardened.sh  NEW — docker run wrapper applying hardened flags

tests/strixnoapi/         NEW — our test suite (>80 unit + integration tests)

NOTICE                    NEW — Apache 2.0 upstream attribution
SECURITY.md               NEW — threat model + disclosure
THREAT_MODEL.md           NEW — STRIDE-ish analysis
MIGRATION.md              NEW — this file
.env.example              NEW — config reference
```

## Modified upstream files

### `pyproject.toml`
- Project renamed `strix-agent` → `strixnoapi`.
- Wheel packages now include both `strix` and `strixnoapi`.
- `[project.scripts] strix` points at `strixnoapi.wrap:cli_main` (adds
  proxy bootstrap before upstream main).
- Added `strix-upstream = "strix.interface.main:main"` as direct passthrough.
- New deps: `fastapi`, `uvicorn`, `httpx`, `zstandard`, `tomli-w`, `questionary`.
- New dev deps: `respx`, `pip-audit`, `pytest-httpx`.
- `[tool.coverage.run] source` + `[tool.pytest.ini_options] --cov` include
  both `strix` and `strixnoapi`.
- `[tool.ruff.lint.per-file-ignores]` extended for legitimate patterns in
  strixnoapi (lazy imports in CLI commands, etc.).
- Added pytest markers: `e2e`, `integration`, `slow`.

### `.gitignore`
- Added: `.claude-session.md`, `.strix-runtime/`, `runs/`, `*.token`,
  `*.sarif.tmp`, `temp-upstream/`.

### Everything else under `strix/`
- **Untouched.** `git diff upstream/main..HEAD -- strix/` = empty.

---

## Functional changes

### How LLM calls are routed

**Upstream:** user sets `STRIX_LLM=openai/gpt-5.4` + `LLM_API_KEY=sk-…`;
`strix/llm/llm.py` calls `litellm.acompletion()` which hits the provider
directly.

**strixnoapi:** user sets `STRIX_CLI_MODE=claude` (or codex, gemini, cursor,
auto). `strixnoapi/wrap.py` runs BEFORE `strix/interface/main.py`:

1. Spawns `strixnoapi/proxy/server.py` as a child process on an ephemeral
   127.0.0.1 port with a UUID bearer token.
2. Sets `OPENAI_API_BASE=http://127.0.0.1:<port>/v1` and
   `OPENAI_API_KEY=<bearer>` and `STRIX_LLM=openai/<cli-model>`.
3. Calls upstream `strix.interface.main:main`.

`strix/llm/llm.py` is 100% unchanged — LiteLLM thinks it's talking to an
OpenAI-compatible endpoint.

### Sandbox flags

Upstream `containers/Dockerfile` builds a Kali-based pentest sandbox with
useful defaults. strixnoapi adds:

- `containers/Dockerfile.hardened` — optional thin overlay that strips
  setuid bits and removes `su`/`sudo`.
- `containers/seccomp.json` — custom seccomp profile denying ptrace,
  keyctl, bpf, perf_event_open, kernel module manipulation, `reboot`.
- `containers/docker-run-hardened.sh` — wrapper applying
  `--cap-drop=ALL --security-opt=no-new-privileges --read-only
  --pids-limit=512 --memory=4g --security-opt=seccomp=…`.

Launch path isn't auto-rewritten — upstream's `strix/runtime/docker_runtime.py`
still composes docker-run invocations. Hardening is opt-in via our wrapper
or by editing the upstream's docker SDK call sites (future: landed upstream
by-commit cherry-pick if deemed generally useful).

---

## Behavioral differences

| Behavior | Upstream | strixnoapi |
|---|---|---|
| Requires API key | Yes | No (with CLI mode set) |
| Requires at least one authenticated CLI | — | Yes (if CLI mode) |
| Persists OAuth tokens | N/A | Never; reads per request |
| Audit log format | Text | JSONL with SHA-256 hash chain |
| Prompt logging | Via telemetry (opt-out) | Opt-in (`STRIX_LOG_PROMPTS=1`), redacted |
| Subcommands | `strix` | `strix setup`, `strix doctor`, `strix resume`, `strix report`, `strix audit verify`, `strix update`, plus upstream's `strix --target ...` |
| Report formats | Markdown | Markdown (upstream) + SARIF 2.1.0 + HTML (ours) |
| Proxy server | N/A | FastAPI on ephemeral 127.0.0.1 port |

---

## Cherry-picking upstream security patches

```bash
git remote add upstream https://github.com/usestrix/strix.git  # first time only
git fetch upstream main
uv run strix update --dry-run                 # shows pending upstream commits
# Review each commit; if it doesn't touch strixnoapi/ files:
git merge upstream/main
# Otherwise cherry-pick individually:
git cherry-pick <commit-sha>
uv run pytest                                 # ensure nothing broke
```

Upstream commits that modify files under `strix/` should merge cleanly
because strixnoapi never edits those files. Conflicts usually mean you
accidentally edited upstream code — revert and put the change in
`strixnoapi/` instead.

---

## Rollback

To fully roll back to upstream behavior without uninstalling:

```bash
unset STRIX_CLI_MODE
export STRIX_LLM=openai/gpt-5.4
export LLM_API_KEY=sk-...
uv run strix --target <...>    # or: uv run strix-upstream --target <...>
```

With `STRIX_CLI_MODE` unset, `wrap.py` is a no-op and the call falls
through unchanged to upstream's main.

---

## Known divergences

- `pyproject.toml.name` differs (`strixnoapi` vs `strix-agent`). The import
  root remains `strix` for upstream + `strixnoapi` for ours.
- Our binary `strix` has a different entry point than upstream. Upstream
  is still reachable via `strix-upstream`.
- Our audit log and run artifacts live under `~/.strix/`; upstream's
  `strix_runs/` output directory is unchanged.
