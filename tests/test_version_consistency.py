"""Prevent drift between HACS manifest, package metadata and changelog."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "thessla_green_modbus" / "manifest.json"


def test_current_version_consistent_across_metadata() -> None:
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project_version = tomllib.load(stream)["project"]["version"]
    assert version == project_version
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{version}]" in changelog
