"""Minimal CycloneDX SBOM generator."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    name: str
    version: str
    purl: str
    type: str = "library"


def collect_python_deps() -> list[Component]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    comps: list[Component] = []
    for pkg in data:
        name = pkg.get("name")
        version = pkg.get("version")
        if name and version:
            comps.append(
                Component(
                    name=name,
                    version=version,
                    purl=f"pkg:pypi/{name}@{version}",
                )
            )
    return comps


def build_sbom(components: list[Component]) -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tools": [{"vendor": "strixnoapi", "name": "sbom", "version": "0.1.0"}],
            "component": {
                "type": "application",
                "name": "strixnoapi",
                "version": _our_version(),
                "properties": [
                    {"name": "python", "value": platform.python_version()},
                    {"name": "platform", "value": platform.platform()},
                ],
            },
        },
        "components": [
            {
                "type": c.type,
                "name": c.name,
                "version": c.version,
                "purl": c.purl,
            }
            for c in components
        ],
    }


def _our_version() -> str:
    try:
        from importlib.metadata import version

        return version("strixnoapi")
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    sbom = build_sbom(collect_python_deps())
    print(json.dumps(sbom, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
