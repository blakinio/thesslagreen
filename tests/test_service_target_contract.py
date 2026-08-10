"""Contract tests for Home Assistant service targeting and error semantics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus.services.dispatch import write_register
from custom_components.thessla_green_modbus.services.schema import REFRESH_DEVICE_DATA_SCHEMA
from custom_components.thessla_green_modbus.services.targets import (
    extract_entity_ids_with_extractor,
    iter_target_coordinators,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


@pytest.mark.asyncio
async def test_async_target_extractor_is_awaited() -> None:
    """The HA async target resolver must be awaited, never closed/discarded."""
    call = SimpleNamespace(data={"device_id": ["device-1"]})
    extractor = AsyncMock(return_value={"sensor.airpack"})

    result = await extract_entity_ids_with_extractor(SimpleNamespace(), call, extractor=extractor)

    assert result == {"sensor.airpack"}
    extractor.assert_awaited_once_with(call)


@pytest.mark.asyncio
async def test_indirect_target_without_entity_id_is_resolved() -> None:
    """Device/area/floor/label targets must not be short-circuited."""
    call = SimpleNamespace(data={"area_id": ["utility_room"]})
    extractor = AsyncMock(return_value={"fan.airpack"})

    result = await extract_entity_ids_with_extractor(SimpleNamespace(), call, extractor=extractor)

    assert result == {"fan.airpack"}
    extractor.assert_awaited_once_with(call)


@pytest.mark.asyncio
async def test_no_loaded_thessla_target_is_validation_error() -> None:
    """A target that resolves only to foreign/unloaded entities is invalid."""
    from custom_components.thessla_green_modbus.services import targets as targets_module

    original = targets_module.extract_entity_ids

    async def fake_extract(_hass, _call):
        return {"sensor.other"}

    targets_module.extract_entity_ids = fake_extract
    try:
        with pytest.raises(ServiceValidationError):
            await iter_target_coordinators(
                SimpleNamespace(),
                SimpleNamespace(data={"area_id": ["utility_room"]}),
                coordinator_getter=lambda _hass, _entity_id: None,
            )
    finally:
        targets_module.extract_entity_ids = original


def test_target_schema_accepts_standard_ha_target_fields() -> None:
    """Entity-service schemas support all HA target dimensions."""
    for field, value in (
        ("entity_id", ["sensor.airpack"]),
        ("device_id", ["device-1"]),
        ("area_id", ["utility_room"]),
        ("floor_id", ["ground_floor"]),
        ("label_id", ["ventilation"]),
    ):
        validated = REFRESH_DEVICE_DATA_SCHEMA({field: value})
        assert validated[field] == value


@pytest.mark.asyncio
async def test_failed_write_raises_home_assistant_error() -> None:
    """A False device write must never look like a successful HA action."""
    coordinator = SimpleNamespace(
        async_write_register=AsyncMock(return_value=False),
    )
    logger = SimpleNamespace(error=lambda *args, **kwargs: None)

    with pytest.raises(HomeAssistantError):
        await write_register(
            coordinator,
            "special_mode",
            1,
            "fan.airpack",
            "set special mode",
            logger,
        )
