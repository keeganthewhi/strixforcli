# strixnoapi — Threat Model

STRIDE-flavored analysis of the adversarial surface introduced by the
subscription-OAuth proxy, sandbox hardening layer, and CLI subcommands.
Scan engine threats (agent loop, tools, prompts) belong to upstream.

---

## Trust boundaries

```
                         ┌──────────────────────────────┐
                         │  user's host (trusted user)  │
  (T1)  Strix agent loop ◄──┐                           │
              │             │                           │
              ▼             │                           │
  (T2)  litellm client ─────┼──► (T3) FastAPI proxy ────┼──► (T4) httpx.AsyncClient
                            │        (127.0.0.1)        │        │
                            │                           │        │
                            │   ~/.<cli>/ OAuth files   │        ▼
                            │          (T5)             │   (T6) Provider API
                            └──────────────┬────────────┘        (Anthropic / OpenAI / Google / Cursor)
                                           │
                            ┌──────────────▼────────────┐
                            │  (T7) Docker sandbox       │ ← (T8) target code / URL
                            │       (tool executor)      │
                            └────────────────────────────┘
```

## Assets

| ID | Asset | Sensitivity |
|---|---|---|
| A1 | CLI OAuth tokens (~/.<cli>/…) | High — grant subscription access |
| A2 | Pentest findings (workspace) | Medium |
| A3 | Host shell (outside sandbox) | High |
| A4 | Target system (A5's system) | High — legal authorization required |
| A5 | Subscription quota | Medium — cost avoidance for user |
| A6 | Audit log | Medium — forensics integrity |

## STRIDE analysis

### Spoofing (S)

| Threat | Mitigation |
|---|---|
| Another local process hits the proxy pretending to be Strix | UUID bearer token on every request; constant-time compare in `auth.py` |
| Attacker in another process impersonates a provider API | httpx uses system TLS cert store; no custom root CAs installed by strixnoapi |
| Stale session token used after user logged out | Proxy reads token fresh per request — logout invalidates on disk |

### Tampering (T)

| Threat | Mitigation |
|---|---|
| Attacker modifies audit log to hide activity | SHA-256 hash chain; `strix audit verify` detects |
| Attacker swaps our proxy binary | Detectable via Python module integrity; deploy via uv + pinned versions |
| Request body altered in transit | Local loopback only — no TLS MITM surface on 127.0.0.1 |
| Upstream Strix code modified to bypass proxy | Upstream is READ-ONLY by policy; `git diff strix/` shows it |

### Repudiation (R)

| Threat | Mitigation |
|---|---|
| User denies running a scan | Audit log has timestamp + hash chain; `strix audit verify` provides integrity proof |
| User denies seeing a finding | Reports are deterministic outputs; SARIF + HTML are byte-stable |

### Information disclosure (I)

| Threat | Mitigation |
|---|---|
| OAuth token logged in audit | `STRIX_LOG_PROMPTS` off by default; redaction pass before log write |
| Model echoes secret from scanned repo | Outbound `scrubadub` + curated pattern redaction |
| Proxy leaks token via error message | `auth.py` never echoes provided tokens; 401 response has no detail body |
| Memory dump of proxy process | Out of scope (requires local root) |
| Sandbox reads OAuth tokens | Docker sandbox does NOT mount `~/.<cli>/` — tokens stay on host |
| Prompt content leaks via OTel export | `STRIX_TELEMETRY=0` default; upstream `telemetry/` already redacts PII |
| Proxy logs full upstream error body | Error bodies truncated at 500 chars; redaction applied |

### Denial of service (D)

| Threat | Mitigation |
|---|---|
| Subscription quota exhaustion | Rate-limit at proxy (30 rpm default, tunable); clear 429 response with retry-after |
| Sandbox fork-bomb | `--pids-limit=512` |
| Sandbox memory exhaustion | `--memory=4g --memory-swap=4g` |
| Enormous prompt DoSes the proxy | 2 MiB prompt cap, 256 KiB per message, HTTP 413 |
| Audit log disk exhaustion | JSONL append — user monitors; future: log rotation |

### Elevation of privilege (E)

| Threat | Mitigation |
|---|---|
| Sandbox breaks out and accesses host | `cap-drop=ALL`, custom seccomp blocks ptrace/keyctl/bpf/perf_event_open/kernel modules/reboot, `--read-only` root, `no-new-privileges`, non-root user (uid 1001), Docker socket not mounted |
| Pentest tool invokes privileged operation | opt-in `NET_RAW`+`NET_ADMIN` via `STRIX_ALLOW_NET_RAW=1` (default on for nmap); tools cannot acquire other caps |
| Seccomp bypass via unmapped syscall | Default `SCMP_ACT_ERRNO` for any syscall not explicitly allowed |
| Proxy child process inherits user privileges | Intentional — proxy runs as user; there is no privilege separation because there's nothing to escalate to |

## Residual risk

1. **Same-user attacker on host.** If an attacker already has code execution
   as the user, they have OAuth tokens directly and strixnoapi cannot help.
2. **Provider API schema drift.** Subscription backends (especially Cursor,
   Codex session API) are not stable public APIs. strixnoapi's `strix doctor`
   surfaces the failure mode early; users can fall back to API-key mode.
3. **ToS compliance.** Using subscription OAuth for programmatic access may
   violate provider Terms of Service. This is a policy risk, not a software
   defense.
4. **Target-originated prompt injection.** A scanned page / file could
   contain instructions that subvert the agent. Heuristic guard reduces
   obvious cases but is not a panacea. Strict mode (`STRIX_INJECTION_STRICT=1`)
   blocks on match.
5. **Checkpoint tarball extraction.** `strix resume` calls `tarfile.extractall`.
   Current defense relies on provenance: we only extract checkpoints we wrote.
   If a user passes an attacker-controlled `.tar.zst`, it could path-traverse.
   Future: add explicit member validation.
6. **Custom seccomp profile blocks a new pentest tool.** Low but non-zero.
   Mitigated by CI running on Ubuntu/macOS matrix; user can edit
   `containers/seccomp.json` if needed.

## Change-trigger list

Things that should cause a threat-model revisit:

- New CLI subscription added (new OAuth flow, new upstream URL).
- Any modification to `strix/` (upstream changes).
- Sandbox architecture change (e.g., replacing Docker with podman).
- Adding persistent state beyond `~/.strix/cli-config.json` and
  `~/.strix/audit/*.jsonl`.
- Adding a new proxy endpoint beyond `/v1/chat/completions`, `/v1/messages`,
  `/v1/models`, `/health`.
- Relaxing any critical invariant listed in `CLAUDE.md`.
