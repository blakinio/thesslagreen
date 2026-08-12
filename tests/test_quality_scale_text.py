# mypy: ignore-errors
"""Risk-focused branch coverage for the text platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus import text as text_module
from custom_components.thessla_green_modbus.text import ThesslaGreenText
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory


def _definition(**extra) -> dict:
    return {
        "register_type": "holding_registers",
        "translation_key": "device_label",
        **extra,
    }


@pytest.mark.asyncio
async def test_setup_filters_capability_missing_and_force_creates(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        text_module.ENTITY_MAPPINGS,
        "text",
        {
            "blocked": _definition(),
            "missing": _definition(),
            "forced": _definition(),
        },
    )
    mock_coordinator.device_client.get_register_map = Mock(
        return_value={"missing": 40, "forced": 41}
    )
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing"}}
    mock_coordinator.device_client.force_full_register_list = True
    monkeypatch.setattr(
        text_module,
        "capability_block_reason",
        Mock(side_effect=lambda name, _caps: "unsupported" if name == "blocked" else None),
    )
    add_entities = Mock()

    await text_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)

    add_entities.assert_called_once()
    entities, update_before_add = add_entities.call_args.args
    assert update_before_add is False
    assert [entity._register_name for entity in entities] == ["missing", "forced"]


@pytest.mark.asyncio
async def test_setup_missing_address_and_entity_metadata(monkeypatch, mock_coordinator):
    monkeypatch.setitem(
        text_module.ENTITY_MAPPINGS,
        "text",
        {"missing": _definition()},
    )
    mock_coordinator.device_client.get_register_map = Mock(return_value={})
    mock_coordinator.device_client.available_registers = {"holding_registers": {"missing"}}
    monkeypatch.setattr(text_module, "capability_block_reason", Mock(return_value=None))
    add_entities = Mock()

    await text_module.async_setup_entry(Mock(), Mock(runtime_data=mock_coordinator), add_entities)
    add_entities.assert_not_called()

    entity = ThesslaGreenText(
        mock_coordinator,
        "device_label",
        42,
        _definition(
            entity_category="diagnostic",
            max_length=24,
            risk_level="advanced",
            risk_category="identity",
            safety_warning="rename device",
        ),
    )
    entity._coordinator_connected = Mock(return_value=True)
    assert entity.available is True
    assert entity._attr_entity_category is EntityCategory.CONFIG
    assert entity._attr_native_max == 24
    assert entity.extra_state_attributes == {
        "risk_level": "advanced",
        "risk_category": "identity",
        "safety_warning": "rename device",
    }


@pytest.mark.asyncio
async def test_write_success_and_runtime_failure(mock_coordinator):
    entity = ThesslaGreenText(mock_coordinator, "device_label", 42, _definition())
    entity._write_register = AsyncMock(return_value=True)
    await entity.async_set_value("AirPack")
    entity._write_register.assert_awaited_once_with("device_label", "AirPack")

    entity._write_register = AsyncMock(side_effect=RuntimeError("write busy"))
    with pytest.raises(HomeAssistantError, match="Failed to set device_label"):
        await entity.async_set_value("AirPack")
