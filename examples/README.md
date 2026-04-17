# Examples

Walk-through scripts and minimal repros.

## Minimal vulnerable target

`vuln_app.py` — a tiny Flask app with three deliberately planted bugs
(SQL injection, command injection, open redirect). Useful for verifying
strixnoapi end-to-end without needing a real codebase.

```bash
# Run the scan against the example app
STRIX_CLI_MODE=claude uv run strix \
  --target examples/ \
  --non-interactive \
  --scan-mode quick

# Export findings
LATEST=$(ls -td strix_runs/*/ | head -1 | xargs -I {} basename {})
uv run strix report $LATEST --format sarif > findings.sarif
uv run strix report $LATEST --format html > findings.html
uv run strix audit verify $LATEST
```

## Expected findings

Strix should report:

- **Critical**: SQL injection in `/login` (`f"… WHERE name='{u}'"`)
- **Critical**: Command injection in `/ping` (`shell=True` with user input)
- **High**: Open redirect in `/go` (unchecked redirect target)

## Running against your own code

```bash
STRIX_CLI_MODE=claude uv run strix \
  --target /path/to/your/repo \
  --target https://your-staging-url.example.com \
  --non-interactive \
  --scan-mode quick
```

Replace `claude` with `codex`, `gemini`, or `cursor` to route through
that subscription. `auto` picks the first authenticated CLI.
