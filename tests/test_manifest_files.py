"""Validate manifest `files` array lists all required static resources."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "thessla_green_modbus"
MANIFEST = COMPONENT / "manifest.json"


def _expected_files() -> list[str]:
    files: list[str] = ["services.yaml", "strings.json"]
    for folder in ("options", "registers", "translations"):
        for path in (COMPONENT / folder).glob("*.json"):
            files.append(f"{folder}/{path.name}")
    return sorted(files)


def test_manifest_files_list_is_complete() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert sorted(manifest["files"]) == _expected_files()

