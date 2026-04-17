"""Subscription-OAuth proxy layer.

Exposes an OpenAI-compatible HTTP API on 127.0.0.1. Strix's litellm client
hits us instead of a real API; per request we translate to the upstream
provider endpoint authenticated with the user's CLI OAuth token.
"""

from __future__ import annotations


__all__ = ["launcher", "server"]
