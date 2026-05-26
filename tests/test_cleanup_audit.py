"""Tests verifying the cleanup/stabilisation audit fixes.

Covers:
- manifest.json pymodbus upper-bound consistency with pyproject.toml
- async_update_options performs only a reload (no double refresh)
- ConfigFlowResult imported directly (no obsolete try/except fallback)
- ThesslaGreenSensor.extra_state_attributes no longer exposes raw_value
- PLATFORMS entries each have a matching platform module on disk
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "thessla_green_modbus"
MANIFEST = COMPONENT / "manifest.json"


# ---------------------------------------------------------------------------
# 1. Dependency consistency — manifest vs pyproject
# ---------------------------------------------------------------------------


def test_manifest_pymodbus_has_upper_bound() -> None:
    """manifest.json must specify pymodbus<4.0 to avoid accidental pymodbus 4.x installs."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reqs = manifest.get("requirements", [])
    pymodbus_req = next((r for r in reqs if r.startswith("pymodbus")), None)
    assert pymodbus_req is not None, "pymodbus not found in manifest requirements"
    assert "<4" in pymodbus_req or "<4.0" in pymodbus_req, (
        f"manifest.json pymodbus requirement lacks upper bound: {pymodbus_req!r}. "
        "Should be 'pymodbus>=3.6.0,<4.0' to match pyproject.toml."
    )


def test_pyproject_and_manifest_pymodbus_consistent() -> None:
    """pyproject.toml and manifest.json must use the same pymodbus constraint."""
    import tomllib

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_reqs = manifest.get("requirements", [])
    pymodbus_manifest = next((r for r in manifest_reqs if r.startswith("pymodbus")), None)

    with open(ROOT / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)

    project_deps = pyproject.get("project", {}).get("dependencies", [])
    pymodbus_pyproject = next((d for d in project_deps if d.startswith("pymodbus")), None)

    assert pymodbus_manifest is not None, "pymodbus missing from manifest requirements"
    assert pymodbus_pyproject is not None, (
        "pymodbus missing from pyproject.toml [project].dependencies"
    )
    assert pymodbus_manifest == pymodbus_pyproject, (
        f"Mismatch: manifest has {pymodbus_manifest!r}, pyproject has {pymodbus_pyproject!r}"
    )


# ---------------------------------------------------------------------------
# 2. PLATFORMS — each declared platform has a matching .py file
# ---------------------------------------------------------------------------


def test_platforms_have_matching_modules() -> None:
    """Every platform in PLATFORMS must have a corresponding platform module file."""
    from custom_components.thessla_green_modbus.const import PLATFORMS

    missing = []
    for platform in PLATFORMS:
        platform_str = str(platform.value) if hasattr(platform, "value") else str(platform)
        module_path = COMPONENT / f"{platform_str}.py"
        if not module_path.exists():
            missing.append(platform_str)

    assert not missing, (
        f"PLATFORMS declares {missing} but no matching .py module(s) found in component directory"
    )


# ---------------------------------------------------------------------------
# 3. async_update_options — only a reload, no double refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_update_options_only_reloads() -> None:
    """async_update_options must reload the entry, not live-patch and double-refresh."""
    from custom_components.thessla_green_modbus import async_update_options

    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.options = {}

    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    entry.runtime_data = coordinator

    await async_update_options(hass, entry)

    hass.config_entries.async_reload.assert_awaited_once_with("test_entry_id")
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_update_options_does_not_call_compute_register_groups() -> None:
    """async_update_options must not call compute_register_groups on coordinator.device_client."""
    from custom_components.thessla_green_modbus import async_update_options

    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.options = {}

    coordinator = MagicMock()
    entry.runtime_data = coordinator

    await async_update_options(hass, entry)

    coordinator.device_client.compute_register_groups.assert_not_called()


# ---------------------------------------------------------------------------
# 4. ConfigFlowResult import — no obsolete try/except fallback
# ---------------------------------------------------------------------------


def test_config_flow_result_direct_import() -> None:
    """ConfigFlowResult must be imported directly from homeassistant.config_entries."""
    import ast

    source = (COMPONENT / "_config_flow" / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                handler_src = ast.unparse(handler)
                if "ConfigFlowResult" in handler_src:
                    pytest.fail(
                        "Found try/except block referencing ConfigFlowResult — "
                        "obsolete HA <2024.4 fallback should have been removed"
                    )

    # Also verify the direct import is present
    import_found = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "homeassistant.config_entries"
        and any(alias.name == "ConfigFlowResult" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert import_found, (
        "ConfigFlowResult must be imported directly from homeassistant.config_entries"
    )


# ---------------------------------------------------------------------------
# 5. ThesslaGreenSensor.extra_state_attributes — no raw_value pollution
#    Checked via AST to avoid importing HA which is not available in this env
# ---------------------------------------------------------------------------


def _sensor_extra_state_attributes_source() -> str:
    """Return the source of ThesslaGreenSensor.extra_state_attributes."""
    import ast

    source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ThesslaGreenSensor":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "extra_state_attributes":
                    return ast.unparse(item)
    return ""


def test_sensor_extra_state_attributes_no_raw_value() -> None:
    """ThesslaGreenSensor.extra_state_attributes source must not assign raw_value."""
    method_src = _sensor_extra_state_attributes_source()
    assert method_src, "Could not find ThesslaGreenSensor.extra_state_attributes in sensor.py"
    assert "raw_value" not in method_src, (
        "'raw_value' was found in ThesslaGreenSensor.extra_state_attributes — it must be removed "
        "to avoid polluting the HA recorder with a debug integer on every poll cycle"
    )


def test_sensor_extra_state_attributes_has_register_debug_keys() -> None:
    """ThesslaGreenSensor.extra_state_attributes should still return register_name/register_type."""
    method_src = _sensor_extra_state_attributes_source()
    assert method_src, "Could not find ThesslaGreenSensor.extra_state_attributes in sensor.py"
    assert "register_name" in method_src, (
        "'register_name' missing from extra_state_attributes — diagnostic register info lost"
    )
    assert "register_type" in method_src, (
        "'register_type' missing from extra_state_attributes — diagnostic register info lost"
    )


# ---------------------------------------------------------------------------
# 6. Coordinator __init__ — no TypeError fallback for config_entry kwarg
# ---------------------------------------------------------------------------


def test_coordinator_init_no_type_error_fallback() -> None:
    """DataUpdateCoordinator.__init__ must receive config_entry kwarg directly."""
    import ast

    source = (COMPONENT / "coordinator" / "coordinator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type and ast.unparse(handler.type) == "TypeError":
                    body_src = "\n".join(ast.unparse(s) for s in handler.body)
                    if "super().__init__" in body_src and "config_entry" not in body_src:
                        pytest.fail(
                            "Found TypeError fallback that re-calls super().__init__ without "
                            "config_entry — obsolete HA <2023 fallback should have been removed"
                        )


# ---------------------------------------------------------------------------
# 7. Entity __init__ — no TypeError fallback for CoordinatorEntity.__init__
# ---------------------------------------------------------------------------


def test_entity_init_no_type_error_fallback() -> None:
    """CoordinatorEntity.__init__ must be called directly without TypeError fallback."""
    import ast

    source = (COMPONENT / "entity.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    try_nodes_with_coordinator_init = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            body_src = "\n".join(ast.unparse(s) for s in node.body)
            if "super().__init__(coordinator)" in body_src:
                try_nodes_with_coordinator_init.append(node)

    assert not try_nodes_with_coordinator_init, (
        "Found try/except wrapping super().__init__(coordinator) in entity.py — "
        "obsolete CoordinatorEntity fallback should have been removed"
    )
