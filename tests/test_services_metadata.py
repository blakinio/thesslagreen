"""Service metadata consistency tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "thessla_green_modbus"


class Loader(yaml.SafeLoader):
    """YAML loader with !include support for services.yaml."""


def _include(loader: Loader, node: yaml.Node):
    file_path = ROOT / loader.construct_scalar(node)
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


Loader.add_constructor("!include", _include)


with open(ROOT / "services.yaml", encoding="utf-8") as f:
    SERVICES_YAML = yaml.load(f, Loader=Loader)  # nosec B506
with open(ROOT / "strings.json", encoding="utf-8") as f:
    STRINGS = json.load(f)
with open(ROOT / "translations" / "en.json", encoding="utf-8") as f:
    EN = json.load(f)
with open(ROOT / "translations" / "pl.json", encoding="utf-8") as f:
    PL = json.load(f)


def _service_field_keys(data: dict, service: str) -> set[str]:
    return set((data.get("services", {}).get(service, {}).get("fields") or {}).keys())


def test_service_and_field_keys_match_metadata() -> None:
    """Every service and field in services.yaml must exist in all metadata files."""
    service_keys = set(SERVICES_YAML.keys())
    for trans in (STRINGS, EN, PL):
        translated_services = set(trans.get("services", {}).keys())
        assert service_keys == translated_services  # nosec B101

        for service in service_keys:
            yaml_fields = set((SERVICES_YAML[service].get("fields") or {}).keys())
            assert yaml_fields == _service_field_keys(trans, service)  # nosec B101


def test_service_translation_structures_match() -> None:
    """Ensure en/pl service metadata structures have matching keys."""

    def compare_keys(en: dict, pl: dict) -> None:
        assert set(en.keys()) == set(pl.keys())  # nosec B101
        for key, en_value in en.items():
            pl_value = pl[key]
            if isinstance(en_value, dict):
                assert isinstance(pl_value, dict)  # nosec B101
                compare_keys(en_value, pl_value)

    compare_keys(EN["services"], PL["services"])
