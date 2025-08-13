"""Tests for ThesslaGreenSelect entity."""

import asyncio
import sys
import types

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))

select_mod = types.ModuleType("homeassistant.components.select")


class SelectEntity:  # pragma: no cover - simple stub
    pass


select_mod.SelectEntity = SelectEntity
sys.modules["homeassistant.components.select"] = select_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.select import (  # noqa: E402
    SELECT_DEFINITIONS,
    ThesslaGreenSelect,
)


def test_select_creation_and_state(mock_coordinator):
    """Test creation and state changes of select entity."""
    mock_coordinator.data["mode"] = 0
    select = ThesslaGreenSelect(mock_coordinator, "mode", SELECT_DEFINITIONS["mode"])
    assert select.current_option == "auto"

    mock_coordinator.data["mode"] = 1
    assert select.current_option == "manual"


def test_select_option_change(mock_coordinator):
    mock_coordinator.data["mode"] = 0
    select = ThesslaGreenSelect(mock_coordinator, "mode", SELECT_DEFINITIONS["mode"])
    asyncio.run(select.async_select_option("manual"))
    mock_coordinator.async_write_register.assert_awaited_with("mode", 1)
    mock_coordinator.async_request_refresh.assert_awaited_once()
