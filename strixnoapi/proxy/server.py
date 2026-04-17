"""FastAPI app — OpenAI + Anthropic compatible facade over CLI-OAuth translators.

Runs as a child process spawned by `strixnoapi.proxy.launcher`. Env vars
carry config into the child (see `ProxySettings.from_env`).
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from strixnoapi.proxy import injection_guard, redaction
from strixnoapi.proxy.audit import AuditLogger
from strixnoapi.proxy.auth import verify_token
from strixnoapi.proxy.credentials import CredentialError, load_oauth
from strixnoapi.proxy.ratelimit import rate_limit_check
from strixnoapi.proxy.settings import ProxySettings
from strixnoapi.proxy.translators import get_translator
from strixnoapi.proxy.validation import flatten_text, validate_request_body


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


log = logging.getLogger("strixnoapi.proxy")


def build_app(settings: ProxySettings | None = None) -> FastAPI:
    if settings is None:
        settings = ProxySettings.from_env()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.audit = AuditLogger(settings.audit_dir / f"proxy-{os.getpid()}.jsonl")
        try:
            yield
        finally:
            with contextlib.suppress(Exception):
                app.state.audit.close()

    app = FastAPI(
        title="strixnoapi-proxy",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    # Populate state immediately for in-process (TestClient) usage that
    # inspects state before a request triggers lifespan.
    app.state.settings = settings
    app.state.audit = AuditLogger(settings.audit_dir / f"proxy-{os.getpid()}.jsonl")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "cli_mode": settings.cli_mode, "version": "0.1.0"}

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return await health()

    @app.get("/v1/models")
    async def list_models(_auth: None = Depends(verify_token)) -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {"id": f"cli/{settings.cli_mode}", "object": "model", "created": 0,
                 "owned_by": "strixnoapi"},
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        _auth: None = Depends(verify_token),
        _rl: None = Depends(rate_limit_check),
    ):
        body = await request.json()
        validate_request_body(
            body,
            max_prompt_bytes=settings.max_prompt_bytes,
            max_message_bytes=settings.max_message_bytes,
        )
        messages = body.get("messages", [])
        injections = injection_guard.scan_messages(messages)
        if injections and injection_guard.is_strict():
            raise HTTPException(400, f"prompt injection patterns detected: {injections}")
        prompt_text = flatten_text(messages)
        _, pii = redaction.redact(prompt_text)
        audit: AuditLogger = app.state.audit
        entry: dict[str, Any] = {
            "kind": "request",
            "cli": settings.cli_mode,
            "endpoint": "chat.completions",
            "prompt_chars": len(prompt_text),
            "model": body.get("model"),
            "stream": bool(body.get("stream")),
            "injection_flags": injections,
            "pii_kinds": pii,
        }
        if settings.log_prompts:
            redacted_prompt, _ = redaction.redact(prompt_text)
            entry["prompt"] = redacted_prompt[:32_000]
        audit.append(entry)

        try:
            oauth = load_oauth(settings.cli_mode)
        except CredentialError as e:
            audit.append({"kind": "error", "code": "credentials", "message": str(e)})
            raise HTTPException(401, str(e)) from e

        translator = get_translator(settings.cli_mode)

        if body.get("stream", False):
            async def gen():
                async for chunk in translator.stream_openai(body, oauth, settings):
                    yield chunk
                audit.append({"kind": "response_end", "streamed": True})
            return StreamingResponse(gen(), media_type="text/event-stream")

        result = await translator.complete_openai(body, oauth, settings)
        audit.append(
            {
                "kind": "response",
                "usage": result.get("usage"),
                "finish_reason": result.get("choices", [{}])[0].get("finish_reason"),
            }
        )
        return JSONResponse(result)

    @app.post("/v1/messages")
    async def anthropic_messages(
        request: Request,
        _auth: None = Depends(verify_token),
        _rl: None = Depends(rate_limit_check),
    ):
        body = await request.json()
        messages = body.get("messages", [])
        if not isinstance(messages, list) or not messages:
            raise HTTPException(400, "messages must be a non-empty list")
        audit: AuditLogger = app.state.audit
        audit.append({"kind": "request", "cli": settings.cli_mode, "endpoint": "messages"})
        try:
            oauth = load_oauth(settings.cli_mode)
        except CredentialError as e:
            raise HTTPException(401, str(e)) from e
        translator = get_translator(settings.cli_mode)
        if body.get("stream", False):
            async def gen():
                async for chunk in translator.stream_anthropic(body, oauth, settings):
                    yield chunk
            return StreamingResponse(gen(), media_type="text/event-stream")
        result = await translator.complete_anthropic(body, oauth, settings)
        audit.append({"kind": "response", "usage": result.get("usage")})
        return JSONResponse(result)

    return app


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = ProxySettings.from_env()
    app = build_app(settings)
    uvicorn.run(
        app,
        host=settings.bind_host,
        port=settings.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
