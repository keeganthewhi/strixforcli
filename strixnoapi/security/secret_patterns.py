"""Secret pattern catalog — re-exported from proxy.redaction for CLI tools."""

from __future__ import annotations

from strixnoapi.proxy.redaction import SECRET_PATTERNS, redact, redact_dict


__all__ = ["SECRET_PATTERNS", "redact", "redact_dict"]
