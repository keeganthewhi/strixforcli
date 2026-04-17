"""Secret redaction — runs on every inbound prompt and outbound completion."""

from __future__ import annotations

import re
from re import Pattern


SECRET_PATTERNS: list[tuple[Pattern[str], str]] = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_access_key"),
    (re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})"), "aws_secret"),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), "github_pat"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{82}"), "github_fine_pat"),
    (re.compile(r"gho_[A-Za-z0-9]{36}"), "github_oauth"),
    (re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9\-_]{80,}"), "anthropic_key"),
    (re.compile(r"sk-ant-oat\d{2}-[A-Za-z0-9\-_]{80,}"), "anthropic_oauth_token"),
    (re.compile(r"sk-proj-[A-Za-z0-9\-_]{40,}"), "openai_project_key"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}(?![A-Za-z0-9])"), "openai_key"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "google_api_key"),
    (re.compile(r"ya29\.[0-9A-Za-z\-_]+"), "google_oauth_access"),
    (
        re.compile(r"eyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}"),
        "jwt",
    ),
    (re.compile(r"-----BEGIN (RSA|OPENSSH|DSA|EC|PGP|PRIVATE) (PRIVATE )?KEY-----"), "private_key"),
    (re.compile(r"sk_live_[A-Za-z0-9]{24,}"), "stripe_live_secret"),
    (re.compile(r"pk_live_[A-Za-z0-9]{24,}"), "stripe_live_publishable"),
    (re.compile(r"rk_live_[A-Za-z0-9]{24,}"), "stripe_restricted"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"), "slack_token"),
    (re.compile(r"glpat-[A-Za-z0-9\-_]{20,}"), "gitlab_pat"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.=]{32,}"), "bearer_token"),
    (re.compile(r"dop_v1_[A-Za-z0-9]{64}"), "digitalocean_token"),
    (re.compile(r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"), "sendgrid_key"),
    (re.compile(r"[A-Za-z0-9]{32}-us[0-9]{1,2}"), "mailchimp_key"),
    (re.compile(r"npm_[A-Za-z0-9]{36}"), "npm_token"),
    (re.compile(r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]+"), "pypi_token"),
    (re.compile(r"hf_[A-Za-z0-9]{32,}"), "huggingface_token"),
]


def redact(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, list_of_pattern_names_matched)."""
    names: list[str] = []
    for pattern, name in SECRET_PATTERNS:
        if pattern.search(text):
            names.append(name)
            text = pattern.sub(f"[REDACTED:{name}]", text)
    return text, names


def redact_dict(obj: object) -> tuple[object, list[str]]:
    all_names: list[str] = []
    if isinstance(obj, str):
        new, names = redact(obj)
        all_names.extend(names)
        return new, all_names
    if isinstance(obj, list):
        out = []
        for item in obj:
            new, names = redact_dict(item)
            out.append(new)
            all_names.extend(names)
        return out, all_names
    if isinstance(obj, dict):
        new_d: dict = {}
        for k, v in obj.items():
            new, names = redact_dict(v)
            new_d[k] = new
            all_names.extend(names)
        return new_d, all_names
    return obj, all_names
