#!/usr/bin/env python3
"""Generate a CycloneDX SBOM for the current Rowlytics workspace."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "SBOM.json"
EXCLUDES = (
    "./.aws-sam/**",
    "./backend/.aws-sam/**",
    "./.github/**",
    "**/.github/**",
    "./playwright-report/**",
    "./test-results/**",
    "./node_modules/**",
    "./function.zip",
    "**/*.exe",
)
DROP_COMPONENT_NAMES = {
    "pre-commit-package",
    "pre_commit_placeholder_package",
}
KNOWN_LICENSE_FIXUPS = {
    "jinja2": [{"license": {"id": "BSD-3-Clause"}}],
}


def _syft_binary() -> str:
    override = os.getenv("SYFT_BIN")
    if override:
        return override

    syft_path = shutil.which("syft")
    if syft_path:
        return syft_path

    raise SystemExit(
        "Syft is required to generate SBOM.json. "
        "Install syft or set the SYFT_BIN environment variable."
    )


def _run_syft() -> None:
    command = [
        _syft_binary(),
        "dir:.",
        "-o",
        f"cyclonedx-json={OUTPUT_PATH}",
    ]
    for pattern in EXCLUDES:
        command.extend(["--exclude", pattern])

    environment = os.environ.copy()
    environment.setdefault("SYFT_CHECK_FOR_APP_UPDATE", "false")
    environment.setdefault("SYFT_FILE_METADATA_SELECTION", "none")
    environment.setdefault("XDG_CACHE_HOME", "/tmp")

    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def _normalize_sbom() -> None:
    data = json.loads(OUTPUT_PATH.read_text())

    components = []
    kept_refs: set[str] = set()
    for component in data.get("components", []):
        name = component.get("name")
        if name in DROP_COMPONENT_NAMES:
            continue
        if not component.get("licenses") and name in KNOWN_LICENSE_FIXUPS:
            component["licenses"] = KNOWN_LICENSE_FIXUPS[name]
        components.append(component)
        bom_ref = component.get("bom-ref")
        if bom_ref:
            kept_refs.add(bom_ref)

    data["components"] = components

    dependencies = []
    for dependency in data.get("dependencies", []):
        ref = dependency.get("ref")
        if ref not in kept_refs:
            continue
        dependency["dependsOn"] = [
            dependency_ref
            for dependency_ref in dependency.get("dependsOn", [])
            if dependency_ref in kept_refs
        ]
        dependencies.append(dependency)

    data["dependencies"] = dependencies
    OUTPUT_PATH.write_text(json.dumps(data, indent=2) + "\n")


def main() -> int:
    _run_syft()
    _normalize_sbom()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
