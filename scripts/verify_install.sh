#!/usr/bin/env bash
# verify_install.sh — end-to-end sanity check for a strixnoapi install.
#
# Usage:
#   scripts/verify_install.sh
#
# Exits 0 if every step succeeds, non-zero on first failure.

set -euo pipefail

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

step() {
  bold ""
  bold "== $* =="
}

fail() {
  red "FAIL: $*"
  exit 1
}

# --------------------------------------------------------------------

step "Python version"
py=$(python --version 2>&1 || true)
echo "  $py"
[[ "$py" =~ 3\.(1[2-9]|[2-9][0-9]) ]] || fail "need Python 3.12+"

step "uv"
uv --version || fail "uv not installed (curl -LsSf https://astral.sh/uv/install.sh | sh)"

step "Docker"
docker --version || fail "docker CLI not on PATH"
docker info >/dev/null 2>&1 || fail "docker daemon not reachable"

step "uv sync"
uv sync --no-dev >/dev/null
uv pip install pytest pytest-asyncio respx httpx >/dev/null
green "dependencies installed"

step "ruff"
uv run ruff check strixnoapi/

step "pytest (strixnoapi)"
uv run pytest tests/strixnoapi/ --no-cov -q

step "strix version"
uv run strix version

step "strix doctor"
uv run strix doctor || {
  red "strix doctor reported issues — continue only if you expected no authenticated CLI"
}

step "proxy smoke (spawn + health + teardown)"
uv run python - <<'PY'
from strixnoapi.proxy.launcher import start_proxy
from pathlib import Path
import urllib.request, json
h = start_proxy('claude', Path.home()/'.strix'/'audit')
req = urllib.request.Request(
    f'http://127.0.0.1:{h.port}/health',
    headers={'Authorization': f'Bearer {h.token}'},
)
with urllib.request.urlopen(req, timeout=3) as r:
    data = json.loads(r.read())
assert data.get('status') == 'ok', data
print(f'  proxy up :{h.port}  status=ok')
h.terminate()
PY

step "audit verify (empty log)"
uv run python - <<'PY'
from strixnoapi.proxy.audit import AuditLogger, verify_chain
from pathlib import Path
p = Path('/tmp/verify-install-audit.jsonl')
p.unlink(missing_ok=True)
with AuditLogger(p) as log:
    log.append({'kind':'test','n':1})
    log.append({'kind':'test','n':2})
ok, n, reason = verify_chain(p)
assert ok, f'chain invalid: {reason}'
assert n == 2
p.unlink()
print(f'  chain verified ({n} entries)')
PY

step "SBOM"
uv run python -m strixnoapi.security.sbom | python -c "
import sys, json
d = json.loads(sys.stdin.read())
assert d['bomFormat'] == 'CycloneDX'
assert d['specVersion'] == '1.5'
print(f'  SBOM: {len(d[\"components\"])} components')
"

step "Runtime fixes (Windows only: npipesocket patch)"
uv run python - <<'PY'
from strixnoapi.runtime import apply_runtime_fixes
apply_runtime_fixes()
import sys
if sys.platform == 'win32':
    from docker.transport import npipesocket
    assert hasattr(npipesocket, '_strixnoapi_original_send'), 'npipesocket not patched'
    print('  npipesocket chunked-write patch: applied')
else:
    print('  non-Windows: no runtime patches needed')
PY

bold ""
green "✓ All verification steps passed. strixnoapi is ready to use."
bold "  Next: STRIX_CLI_MODE=<claude|codex|gemini|cursor> uv run strix --target <url-or-repo> --non-interactive"
