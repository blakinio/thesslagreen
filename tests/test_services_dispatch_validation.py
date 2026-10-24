from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from custom_components.thessla_green_modbus.services.dispatch import (
    refresh_and_log_success,
    write_mapped_optional_register,
    write_optional_register,
    write_register,
    write_register_batch,
    write_register_steps,
)
from custom_components.thessla_green_modbus.services.validation import (
    BAUD_MAP,
    filter_reset_value,
    iter_air_quality_writes,
    normalize_modbus_options,
    normalize_option,
    pressure_test_payload,
    reset_settings_registers,
    validate_bypass_temperature_range,
    validate_gwc_temperature_range,
)
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ConnectionException


@pytest.mark.asyncio
async def test_write_register_handles_connection_exception():
    coordinator = SimpleNamespace(
        async_write_register=AsyncMock(side_effect=ConnectionException("x"))
    )
    logger = SimpleNamespace(error=MagicMock(), info=MagicMock())

    with pytest.raises(HomeAssistantError):
        await write_register(coordinator, "reg", 1, "climate.a", "action", logger)

    logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_and_log_success_requests_refresh_and_logs():
    coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
    logger = SimpleNamespace(info=MagicMock())

    await refresh_and_log_success(coordinator, logger, "Did %s", "thing")

    coordinator.async_request_refresh.assert_awaited_once()
    logger.info.assert_called_once_with("Did %s", "thing")


@pytest.mark.asyncio
async def test_write_optional_register_skips_none_value():
    write_func = AsyncMock()
    logger = SimpleNamespace(error=MagicMock())
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


@pytest.mark.asyncio
async def test_write_register_propagates_cancellation():
    coordinator = SimpleNamespace(
        async_write_register=AsyncMock(side_effect=asyncio.CancelledError)
    )
    logger = SimpleNamespace(error=MagicMock())

    with pytest.raises(asyncio.CancelledError):
        await write_register(coordinator, "reg", 1, "climate.a", "action", logger)

    logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_write_optional_register_reports_failed_write():
    write_func = AsyncMock(return_value=False)
    logger = SimpleNamespace(error=MagicMock())
    coordinator = object()

    result = await write_optional_register(
        coordinator,
        "reg",
        5,
        "climate.a",
        "act",
        "err %s",
        write_func,
        logger,
    )

    assert result is False
    write_func.assert_awaited_once_with(coordinator, "reg", 5, "climate.a", "act")
    logger.error.assert_called_once_with("err %s", "climate.a")


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
    logger = SimpleNamespace(error=MagicMock())

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


@pytest.mark.asyncio
async def test_write_register_batch_logs_and_stops_on_failure():
    write_func = AsyncMock(side_effect=[True, False])
    logger = SimpleNamespace(error=MagicMock())

    result = await write_register_batch(
        object(),
        [("r1", 1), ("r2", 2)],
        "climate.a",
        "action",
        write_func,
        logger,
        {"r1": "err1 %s", "r2": "err2 %s"},
    )

    assert result is False
    assert write_func.await_count == 2
    logger.error.assert_called_once_with("err2 %s", "climate.a")


@pytest.mark.asyncio
async def test_write_register_steps_skips_optional_none_and_stops_on_failure():
    write_func = AsyncMock(side_effect=[True, False])
    logger = SimpleNamespace(error=MagicMock())

    result = await write_register_steps(
        object(),
        [
            ("required", 1, False, "required err %s"),
            ("optional", None, True, "optional err %s"),
            ("required_2", 2, False, "required2 err %s"),
        ],
        "climate.a",
        "action",
        write_func,
        logger,
    )

    assert result is False
    assert write_func.await_count == 2
    logger.error.assert_called_once_with("required2 err %s", "climate.a")


def test_reset_settings_registers_all_settings():
    assert reset_settings_registers("all_settings") == [
        ("hard_reset_settings", 1),
        ("hard_reset_schedule", 1),
    ]


def test_filter_reset_value_uses_normalized_option():
    assert filter_reset_value(normalize_option, "thessla_green_modbus.filter_type_cleanpad") == 3


def test_pressure_test_payload_builds_day_and_time():
    now = SimpleNamespace(weekday=lambda: 1, hour=9, minute=7)
    assert pressure_test_payload(now) == [
        ("pres_check_day_4432", 1),
        ("pres_check_time_ggmm", "09:07"),
    ]


@pytest.mark.parametrize("batch", [1, 2, 3, 16])
def test_device_name_payload_survives_batch_chunking(batch):
    """Every character lands at its own word, whatever the FC16 batch size."""
    from custom_components.thessla_green_modbus.core.write_path import encode_write_value
    from custom_components.thessla_green_modbus.registers.loader import get_register_definition
    from custom_components.thessla_green_modbus.registers.read_planner import (
        chunk_register_values,
    )

    definition = get_register_definition("device_name")
    encoded, _ = encode_write_value("device_name", definition, "ABCDEFGHIJ", 0)
    written = {}
    for start, chunk in chunk_register_values(definition.address, encoded, batch):
        for index, word in enumerate(chunk):
            written[start + index] = word

    assert sorted(written) == list(range(8144, 8152))
    payload = b"".join(written[a].to_bytes(2, "big") for a in sorted(written))
    assert payload == b"ABCDEFGHIJ\x00\x00\x00\x00\x00\x00"


def test_iter_air_quality_writes_builds_optional_steps_with_register_map():
    steps = iter_air_quality_writes(
        {"co2_low": 500, "co2_medium": None, "co2_high": 1000, "humidity_target": 45},
        {
            "co2_low": "co2_low_reg",
            "co2_medium": "co2_medium_reg",
            "co2_high": "co2_high_reg",
            "humidity_target": "humidity_target_reg",
        },
    )

    assert steps == [
        ("co2_low_reg", 500, True, "Failed to set co2_low for %s"),
        ("co2_medium_reg", None, True, "Failed to set co2_medium for %s"),
        ("co2_high_reg", 1000, True, "Failed to set co2_high for %s"),
        ("humidity_target_reg", 45, True, "Failed to set humidity_target for %s"),
    ]
