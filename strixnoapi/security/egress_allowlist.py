"""Network egress allowlist — compute per-scan iptables rules."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class EgressPolicy:
    allowed_hosts: tuple[str, ...]
    default_deny: bool = True

    def as_iptables_rules(self) -> list[str]:
        rules: list[str] = []
        if self.default_deny:
            for host in self.allowed_hosts:
                rules.append(f"-A OUTPUT -d {host} -j ACCEPT")
            rules.append("-A OUTPUT -d 127.0.0.0/8 -j ACCEPT")
            rules.append("-A OUTPUT -d 10.0.0.0/8 -j ACCEPT")
            rules.append("-A OUTPUT -d 172.16.0.0/12 -j ACCEPT")
            rules.append("-A OUTPUT -d 192.168.0.0/16 -j ACCEPT")
            rules.append("-A OUTPUT -j DROP")
        return rules


def policy_for_scan(target_url: str, extra_allowed: list[str] | None = None) -> EgressPolicy:
    hosts: list[str] = []
    parsed = urlparse(target_url) if target_url else None
    if parsed and parsed.hostname:
        hosts.append(parsed.hostname)
    if extra_allowed:
        hosts.extend(extra_allowed)
    return EgressPolicy(allowed_hosts=tuple(hosts))
