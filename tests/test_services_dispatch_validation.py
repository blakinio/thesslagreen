from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.services_dispatch import (
    refresh_and_log_success,
    write_mapped_optional_register,
    write_optional_register,
    write_register,
)
from custom_components.thessla_green_modbus.services_validation import (
    BAUD_MAP,
    normalize_modbus_options,
    normalize_option,
    validate_bypass_temperature_range,
    validate_gwc_temperature_range,
)


@pytest.mark.asyncio
async def test_write_register_handles_connection_exception():
    coordinator = SimpleNamespace(async_write_register=AsyncMock(side_effect=ConnectionException("x")))
    logger = SimpleNamespace(error=AsyncMock(), info=AsyncMock())

    result = await write_register(coordinator, "reg", 1, "climate.a", "action", logger)

    assert result is False
    logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_and_log_success_requests_refresh_and_logs():
    coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
    logger = SimpleNamespace(info=AsyncMock())

    await refresh_and_log_success(coordinator, logger, "Did %s", "thing")

    coordinator.async_request_refresh.assert_awaited_once()
    logger.info.assert_called_once_with("Did %s", "thing")


@pytest.mark.asyncio
async def test_write_optional_register_skips_none_value():
    write_func = AsyncMock()
    logger = SimpleNamespace(error=AsyncMock())
    coordinator = object()

    result = await write_optional_register(
        coordinator,
        "reg",
        None,
        "climate.a",
        "act",
        "err %s",
        write_func,
        logger,
    )

    assert result is True
    write_func.assert_not_awaited()


def test_validate_gwc_temperature_range_rejects_equal_values():
    with pytest.raises(vol.Invalid):
        validate_gwc_temperature_range({"min_air_temperature": 10.0, "max_air_temperature": 10.0})


def test_validate_bypass_temperature_range_rejects_out_of_range():
    with pytest.raises(vol.Invalid):
        validate_bypass_temperature_range({"min_outdoor_temperature": -21.0})


def test_normalize_option_removes_domain_and_prefix():
    assert normalize_option("thessla_green_modbus.modbus_parity_even") == "even"


def test_normalize_modbus_options_returns_normalized_values():
    port, baud, parity, stop_bits = normalize_modbus_options(
        normalize_option,
        {
            "port": "thessla_green_modbus.modbus_port_air_b",
            "baud_rate": "thessla_green_modbus.modbus_baud_rate_115200",
            "parity": "thessla_green_modbus.modbus_parity_even",
            "stop_bits": "thessla_green_modbus.modbus_stop_bits_2",
        },
    )
    assert (port, baud, parity, stop_bits) == ("air_b", "115200", "even", "2")


@pytest.mark.asyncio
async def test_write_mapped_optional_register_maps_and_writes():
    write_func = AsyncMock(return_value=True)
    logger = SimpleNamespace(error=AsyncMock())

    coordinator = object()
    result = await write_mapped_optional_register(
        coordinator,
        "uart_0_baud",
        "115200",
        BAUD_MAP,
        "climate.a",
        "act",
        "err %s",
        write_func,
        logger,
    )

    assert result is True
    write_func.assert_awaited_once_with(coordinator, "uart_0_baud", 8, "climate.a", "act")
