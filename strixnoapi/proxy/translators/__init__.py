"""Per-CLI translators that speak the upstream LLM API using OAuth tokens."""

from __future__ import annotations

from strixnoapi.proxy.translators.base import BaseTranslator


def get_translator(cli_mode: str) -> BaseTranslator:
    cli_mode = cli_mode.lower()
    if cli_mode == "claude":
        from strixnoapi.proxy.translators.claude_code import ClaudeCodeTranslator

        return ClaudeCodeTranslator()
    if cli_mode == "codex":
        from strixnoapi.proxy.translators.codex import CodexTranslator

        return CodexTranslator()
    if cli_mode == "gemini":
        from strixnoapi.proxy.translators.gemini import GeminiTranslator

        return GeminiTranslator()
    if cli_mode == "cursor":
        from strixnoapi.proxy.translators.cursor import CursorTranslator

        return CursorTranslator()
    msg = f"unknown cli_mode: {cli_mode!r}"
    raise ValueError(msg)


__all__ = ["BaseTranslator", "get_translator"]
