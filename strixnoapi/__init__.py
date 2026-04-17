"""strixnoapi — CLI-subscription-backed Strix.

Upstream strix is untouched; this package sits alongside it and routes
LiteLLM calls through a local OAuth-backed HTTP proxy, adds hardened
sandboxing, interactive setup, checkpointing, and richer reports.
"""

from __future__ import annotations


__version__ = "0.1.0"

__all__ = ["__version__"]
