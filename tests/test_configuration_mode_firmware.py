"""A readable command register must not bypass the AFC firmware contract."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus.device_profile import configuration_command_block_reason
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from custom_components.thessla_green_modbus.services import handlers_maintenance as maintenance
from homeassistant.exceptions import ServiceValidationError

from tests.helpers_coordinator import make_coordinator


@pytest.mark.parametrize("family", ["airpack_home", "airpack4"])
@pytest.mark.parametrize(
    "firmware,blocked",
    [
        ("3.11", True),
        ("3.99", True),
        ("4.74", True),
        ("4.75", False),
        (" v4.89.1 ", False),
        ("5.0", False),
        ("Unknown", True),
        (None, True),
    ],
)
def test_afc_command_version_boundary(family, firmware, blocked):
    assert bool(configuration_command_block_reason(family, firmware, 65)) is blocked
    for command in (0, 47):
        assert configuration_command_block_reason(family, firmware, command) is None


def test_unknown_family_cannot_select_afc_command():
    assert configuration_command_block_reason("unspecified", "4.89", 65)


@pytest.mark.parametrize("raw", [False, True])
async def test_311_command_rejected_before_connection(raw):
    device = make_coordinator()
    device.entry = SimpleNamespace(options={"device_family": "airpack_home"})
    device.device_client.device_info["firmware"] = "3.11"
    device._ensure_connection = AsyncMock()
    if raw:
        result = await device.async_write_registers(13, [65], refresh=False)
        assert result is False
    else:
        with pytest.raises(ValueError, match=r"4\.75"):
            await device.async_write_register("configuration_mode", 65, refresh=False)
    device._ensure_connection.assert_not_awaited()


async def test_311_service_rejected_even_if_write_dependency_would_succeed():
    device = SimpleNamespace(
        entry=SimpleNamespace(options={"device_family": "airpack_home"}),
        device_client=SimpleNamespace(
            device_info={"firmware": "3.11"},
            available_registers={"holding_registers": {"configuration_mode"}},
        ),
    )
    deps = SimpleNamespace(
        iter_target_coordinators=AsyncMock(return_value=[("climate.unit", device)]),
        write_register=AsyncMock(return_value=True),
        logger=Mock(),
    )
    handler = maintenance._build_start_pressure_test_handler(object(), deps)
    with pytest.raises(ServiceValidationError, match=r"4\.75"):
        await handler(
            SimpleNamespace(data={"test_type": "afc_and_duct", "confirm_equipment": True})
        )
    deps.write_register.assert_not_awaited()


@pytest.mark.parametrize("firmware,exposed", [("3.11", False), ("4.75", True)])
def test_select_offers_only_supported_commands(mock_coordinator, firmware, exposed):
    mock_coordinator.entry = SimpleNamespace(options={"device_family": "airpack_home"})
    mock_coordinator.device_client.device_info["firmware"] = firmware
    entity = ThesslaGreenSelect(
        mock_coordinator,
        "configuration_mode",
        13,
        {
            "translation_key": "configuration_mode",
            "states": {"normal": 0, "duct_filter_pressure": 47, "afc_filter_pressure": 65},
        },
    )
    assert ("afc_filter_pressure" in entity.options) is exposed
    assert "normal" in entity.options and "duct_filter_pressure" in entity.options
    assert entity._optimistic_enabled is False
