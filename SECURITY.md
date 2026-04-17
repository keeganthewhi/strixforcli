# Security Policy — strixnoapi

## Scope

strixnoapi is a fork of [`usestrix/strix`](https://github.com/usestrix/strix).
Upstream handles reports for anything in the scan engine (`strix/` directory).
strixnoapi is responsible for:

- `strixnoapi/proxy/` — the subscription-OAuth proxy
- `strixnoapi/security/` — sandbox profile, permission gate, redaction
- `strixnoapi/interface/` — the CLI subcommands (setup, doctor, resume, …)
- `containers/Dockerfile.hardened`, `containers/seccomp.json`,
  `containers/docker-run-hardened.sh`

## Threat model (summary)

See `THREAT_MODEL.md` for the full STRIDE-ish analysis. Top concerns:

1. **OAuth token exfiltration** — tokens live in `~/.<cli>/…` with 0o600
   permissions. The proxy reads them on every request and never copies them
   into config, logs, or the audit file. An attacker with filesystem access
   as the same user already has the tokens; out of scope.
2. **Prompt injection** — target code / crawled pages may contain adversarial
   text meant to subvert the pentest agent. Mitigated by scrubadub +
   curated pattern redaction on inbound prompts, and heuristic `injection_guard`
   which flags (or in strict mode blocks) known override phrases.
3. **Sandbox escape** — the pentest sandbox has many tools and ambient
   privileges needed to probe targets. Hardened with `cap-drop=ALL`, custom
   seccomp (denies ptrace, keyctl, bpf, perf_event_open, kernel-module ops,
   reboot), `--read-only` root, `--pids-limit=512`, `--memory=4g`,
   `no-new-privileges`, non-root user. Docker socket NEVER mounted inside.
4. **Lateral network movement from sandbox** — per-scan egress allowlist
   (`strixnoapi/security/egress_allowlist.py`) restricts outbound traffic
   to the target host + LLM proxy. Private RFC1918 ranges allowed by default
   to reach `host.docker.internal`.
5. **Audit log tampering** — hash-chained JSONL. `strix audit verify` detects
   any modification between entries. Does not prevent deletion of the file
   (that requires a separate append-only store; future work).
6. **Proxy local exposure** — bound to `127.0.0.1`, not `0.0.0.0`.
   Bearer-token auth required on every request (not just auth-exempt
   `/health`). Rate-limited 30 rpm default.
7. **Secret leakage via model echoing** — the upstream model may echo secrets
   from the scanned repo back in its responses. Outbound responses are
   redacted with the same curated pattern set applied to inbound prompts.

## Non-goals (out of scope)

- Defending against a root-local attacker on the user's host.
- Preventing the user from scanning systems they aren't authorized to test
  (this is an operational responsibility, not a software boundary).
- Stopping model providers from changing their authentication / API
  contracts; `strix doctor` surfaces breakage quickly.
- Hiding the fact that strixnoapi is routing through a subscription from
  the provider. ToS compliance is the user's responsibility.

## Disclosure

**Preferred**: open a private security advisory on the strixnoapi GitHub
repo. If that's not available, email the maintainer listed in `NOTICE`.

**Upstream Strix issues** (anything under `strix/`) should be reported to
https://github.com/usestrix/strix/security/advisories/new per their policy.

**Response SLA**:
- Acknowledge within 3 business days.
- Triage severity within 7 business days.
- Patch critical / high issues within 30 days (CVSS ≥ 7.0).
- Patch medium within 90 days.

## Security-relevant environment variables

| Variable | Default | Effect |
|---|---|---|
| `STRIX_ENFORCE_PERMISSIONS` | `1` | Refuse to start if config files are loose (`0o6xx`). Set `0` only on platforms that can't enforce. |
| `STRIX_ENFORCE_WINDOWS_ACL` | `0` | Enable NTFS ACL check (requires pywin32). |
| `STRIX_LOG_PROMPTS` | `0` | Write redacted prompts to audit log. Off for privacy. |
| `STRIX_INJECTION_STRICT` | `0` | Block requests matching injection heuristics with HTTP 400 (vs just logging). |
| `STRIX_ALLOW_NET_RAW` | `1` | Add `NET_RAW` + `NET_ADMIN` capabilities to sandbox (required for some nmap modes). Set `0` for stricter sandbox with reduced tool coverage. |
| `STRIX_PROXY_RATE_LIMIT` | `30` | Requests per minute. Lower for defense-in-depth. |

## Dependency CVE posture

- `uv pip` + `uv.lock` pin transitive deps. Run `pip-audit` (dev dep) before
  release.
- Upstream Strix tracks its own dep audit; see upstream.
- `osv-scanner` and `pip-audit` run in CI on a nightly schedule (see
  `.github/workflows/cve-audit.yml`).

## Cryptographic primitives

- Audit hash chain: SHA-256.
- Proxy bearer token: 256-bit URL-safe random (`secrets.token_urlsafe(32)`).
- No custom crypto. No KDF, signing, or envelope crypto in this codebase.
