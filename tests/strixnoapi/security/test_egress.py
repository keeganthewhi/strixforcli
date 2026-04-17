"""Egress allowlist policy."""

from __future__ import annotations

from strixnoapi.security.egress_allowlist import policy_for_scan


def test_extracts_host():
    p = policy_for_scan("https://example.com:8080/path")
    assert "example.com" in p.allowed_hosts


def test_extra_allowed():
    p = policy_for_scan("https://app.com", extra_allowed=["127.0.0.1", "logs.com"])
    assert "app.com" in p.allowed_hosts
    assert "logs.com" in p.allowed_hosts


def test_iptables_rules_deny_by_default():
    p = policy_for_scan("https://target.com")
    rules = p.as_iptables_rules()
    assert any("target.com" in r for r in rules)
    assert any(r == "-A OUTPUT -j DROP" for r in rules)


def test_private_subnets_allowed():
    p = policy_for_scan("https://target.com")
    rules = p.as_iptables_rules()
    assert any("127.0.0.0/8" in r for r in rules)
    assert any("10.0.0.0/8" in r for r in rules)
