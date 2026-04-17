"""Prompt-injection heuristics.

Flags (but does not block by default) suspicious strings coming from user /
target input that try to subvert the system prompt. In strict mode (env
`STRIX_INJECTION_STRICT=1`) matches cause a 400.
"""

from __future__ import annotations

import os
import re


PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)ignore (the |all )?(previous|prior|above|earlier) (instructions|prompts)"),
     "override_previous"),
    (re.compile(r"(?i)disregard (the |all )?(previous|prior|above) (instructions|system)"),
     "disregard_previous"),
    (re.compile(r"(?i)you are now (a |an )?(different|unrestricted|dan|do anything)"),
     "role_hijack"),
    (re.compile(r"(?i)reveal (your |the )?(system|initial) prompt"),
     "system_prompt_leak"),
    (re.compile(r"(?i)print (all |the )?(env|environment|secret|token|api[\s_-]?key)s?"),
     "secret_exfil"),
    (re.compile(r"<\|im_(start|end)\|>"), "chat_template_injection"),
    (re.compile(r"(?i)</?system>"), "system_tag_injection"),
    (re.compile(r"\bBEGIN RSA PRIVATE KEY\b"), "key_injection"),
]


def scan(text: str) -> list[str]:
    matches: list[str] = []
    for pattern, name in PATTERNS:
        if pattern.search(text):
            matches.append(name)
    return matches


def scan_messages(messages: list[dict]) -> list[str]:
    all_matches: list[str] = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            all_matches.extend(scan(content))
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        all_matches.extend(scan(text))
    return all_matches


def is_strict() -> bool:
    return os.environ.get("STRIX_INJECTION_STRICT", "0") == "1"
