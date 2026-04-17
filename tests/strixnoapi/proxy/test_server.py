"""FastAPI server integration — TestClient against mocked translators."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from strixnoapi.proxy.ratelimit import reset_for_tests
from strixnoapi.proxy.server import build_app
from strixnoapi.proxy.settings import ProxySettings


def _make_client(tmp_home: Path, cli_mode: str = "claude") -> TestClient:
    reset_for_tests()
    audit_dir = tmp_home / ".strix" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    settings = ProxySettings(
        port=9000,
        token="test-token",
        cli_mode=cli_mode,
        audit_dir=audit_dir,
        rate_limit_rpm=60,
    )
    app = build_app(settings)
    return TestClient(app)


def test_health_no_auth_needed(tmp_home, claude_creds):
    client = _make_client(tmp_home)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["cli_mode"] == "claude"


def test_rejects_missing_bearer(tmp_home, claude_creds):
    client = _make_client(tmp_home)
    r = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401


def test_rejects_wrong_bearer(tmp_home, claude_creds):
    client = _make_client(tmp_home)
    r = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer not-the-right-token"},
    )
    assert r.status_code == 401


@respx.mock
def test_full_chat_completion_path(tmp_home, claude_creds):
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "stop_reason": "end_turn",
            },
        )
    )
    client = _make_client(tmp_home)
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["choices"][0]["message"]["content"] == "ok"


def test_validation_rejects_empty_messages(tmp_home, claude_creds):
    client = _make_client(tmp_home)
    r = client.post(
        "/v1/chat/completions",
        json={"messages": []},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 400


def test_models_endpoint(tmp_home, claude_creds):
    client = _make_client(tmp_home)
    r = client.get("/v1/models", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "list"
    assert data["data"][0]["id"] == "cli/claude"
