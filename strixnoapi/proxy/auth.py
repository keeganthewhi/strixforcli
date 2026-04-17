"""Bearer-token auth middleware.

Proxy is bound to 127.0.0.1 but any local process could still hit it;
the bearer token is the second barrier against same-host unauthorized use.
"""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request


if TYPE_CHECKING:
    from strixnoapi.proxy.settings import ProxySettings


EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/healthz", "/"})


def verify_token(request: Request) -> None:
    if request.url.path in EXEMPT_PATHS:
        return
    settings: ProxySettings = request.app.state.settings
    header = request.headers.get("authorization", "")
    provided = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not provided:
        provided = request.headers.get("x-api-key", "").strip()
    if not provided or not hmac.compare_digest(provided, settings.token):
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")
