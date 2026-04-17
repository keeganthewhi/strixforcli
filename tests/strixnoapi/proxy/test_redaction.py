"""Secret pattern redaction."""

from __future__ import annotations

from strixnoapi.proxy.redaction import redact, redact_dict


def test_redacts_aws_access_key():
    text = "my AKIAIOSFODNN7EXAMPLE is leaked"
    out, names = redact(text)
    assert "AKIA" not in out
    assert "[REDACTED:aws_access_key]" in out
    assert "aws_access_key" in names


def test_redacts_github_pat():
    text = "token ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    out, names = redact(text)
    assert "ghp_" not in out
    assert "github_pat" in names


def test_redacts_jwt():
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefg_hijk"
    out, names = redact(text)
    assert "eyJhbGci" not in out
    assert "jwt" in names


def test_redacts_private_key_header():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----"
    out, names = redact(text)
    assert "BEGIN RSA PRIVATE KEY" not in out
    assert "private_key" in names


def test_nothing_to_redact():
    text = "hello world, nothing secret here"
    out, names = redact(text)
    assert out == text
    assert names == []


def test_redact_dict_recursive():
    obj = {
        "user": "alice",
        "creds": {"token": "ghp_abcdefghijklmnopqrstuvwxyz0123456789"},
        "logs": ["fine", "also fine", "AKIAIOSFODNN7EXAMPLE"],
    }
    out, names = redact_dict(obj)
    assert "ghp_" not in str(out)
    assert "AKIA" not in str(out)
    assert "github_pat" in names
    assert "aws_access_key" in names


def test_anthropic_api_key_pattern():
    k = "sk-ant-api03-" + "A" * 80
    text = f"key={k}"
    out, names = redact(text)
    assert k not in out
    assert "anthropic_key" in names
