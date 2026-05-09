"""Validate required static resources exist on disk.

The `files` key was removed from manifest.json because it is not a valid HA
manifest field (not in homeassistant.loader.Manifest) and causes hassfest to
reject the integration.  HACS installs the entire custom_components/<domain>/
directory so all files within it are included automatically.

This test replaces the old manifest["files"] completeness check with a direct
on-disk existence check for every static resource that must be present for the
integration to function correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "thessla_green_modbus"
MANIFEST = COMPONENT / "manifest.json"


def _expected_files() -> list[str]:
    files: list[str] = ["services.yaml", "strings.json"]
    for folder in ("options", "registers", "translations"):
        files.extend(f"{folder}/{path.name}" for path in (COMPONENT / folder).glob("*.json"))
    return sorted(files)


def test_manifest_does_not_have_files_key() -> None:
    """Confirm that the non-HA 'files' key has been removed from manifest.json.

    hassfest rejects unknown manifest keys, so this key must not be present.
    HACS installs the whole custom_components/<domain>/ directory by default.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "files" not in manifest, (
        "'files' is not a valid HA manifest key and must not be present in manifest.json. "
        "HACS installs all files in custom_components/<domain>/ automatically."
    )


def test_required_static_files_exist_on_disk() -> None:
    """All static resources required by the integration must exist on disk."""
    missing = [f for f in _expected_files() if not (COMPONENT / f).exists()]
    assert not missing, f"Missing required integration files: {missing}"
