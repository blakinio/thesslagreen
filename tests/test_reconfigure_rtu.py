"""Regression tests for transport-aware reconfiguration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus._config_flow.reconfigure import (
    build_reconfigure_updates,
)
from custom_components.thessla_green_modbus._config_flow.schema import (
    build_reconfigure_schema,
)
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from custom_components.thessla_green_modbus.const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_TYPE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
)
from homeassistant.const import CONF_HOST, CONF_PORT


def test_reconfigure_schema_exposes_rtu_endpoint_fields() -> None:
    """RTU entries must be reconfigurable without fake TCP host/port fields."""
    schema = build_reconfigure_schema(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
            CONF_SERIAL_PORT: "/dev/serial/by-id/airpack",
            CONF_BAUD_RATE: 19200,
            CONF_PARITY: "even",
            CONF_STOP_BITS: 2,
            CONF_SLAVE_ID: 10,
        }
    )

    result = schema(
        {
            CONF_SERIAL_PORT: "/dev/serial/by-id/airpack-new",
            CONF_BAUD_RATE: 38400,
            CONF_PARITY: "none",
            CONF_STOP_BITS: 1,
            CONF_SLAVE_ID: 0,
        }
    )

    assert result[CONF_SERIAL_PORT] == "/dev/serial/by-id/airpack-new"
    assert result[CONF_BAUD_RATE] == 38400
    assert result[CONF_PARITY] == "none"
    assert result[CONF_STOP_BITS] == 1
    assert result[CONF_SLAVE_ID] == 0
    assert CONF_HOST not in result
    assert CONF_PORT not in result


def test_reconfigure_updates_keep_transport_specific_fields() -> None:
    """TCP and RTU updates must only mutate fields belonging to that transport."""
    tcp_updates = build_reconfigure_updates(
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP},
        {CONF_HOST: "airpack.local", CONF_PORT: 1502, CONF_SLAVE_ID: 3},
    )
    assert tcp_updates == {CONF_HOST: "airpack.local", CONF_PORT: 1502, CONF_SLAVE_ID: 3}

    rtu_updates = build_reconfigure_updates(
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU},
        {
            CONF_SERIAL_PORT: "/dev/serial/by-id/airpack",
            CONF_BAUD_RATE: 9600,
            CONF_PARITY: "none",
            CONF_STOP_BITS: 1,
            CONF_SLAVE_ID: 10,
        },
    )
    assert rtu_updates == {
        CONF_SERIAL_PORT: "/dev/serial/by-id/airpack",
        CONF_BAUD_RATE: 9600,
        CONF_PARITY: "none",
        CONF_STOP_BITS: 1,
        CONF_SLAVE_ID: 10,
    }


@pytest.mark.asyncio
async def test_async_reconfigure_applies_rtu_endpoint_update() -> None:
    """The HA reconfigure step must persist validated RTU connection settings."""
    entry = SimpleNamespace(
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
            CONF_SERIAL_PORT: "/dev/serial/by-id/old",
            CONF_BAUD_RATE: 9600,
            CONF_PARITY: "none",
            CONF_STOP_BITS: 1,
            CONF_SLAVE_ID: 10,
        },
        unique_id=None,
    )
    user_input = {
        CONF_SERIAL_PORT: "/dev/serial/by-id/new",
        CONF_BAUD_RATE: 19200,
        CONF_PARITY: "even",
        CONF_STOP_BITS: 2,
        CONF_SLAVE_ID: 11,
    }

    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow._get_reconfigure_entry = MagicMock(return_value=entry)  # type: ignore[method-assign]
    flow.async_update_and_abort = MagicMock(return_value={"type": "abort"})  # type: ignore[method-assign]

    info = {"device_info": {}, "scan_result": {}}
    with patch(
        "custom_components.thessla_green_modbus._config_flow._process_user_submission_impl",
        new=AsyncMock(return_value=(info, {})),
    ):
        result = await flow.async_step_reconfigure(user_input)

    assert result == {"type": "abort"}
    flow.async_update_and_abort.assert_called_once_with(  # type: ignore[attr-defined]
        entry,
        unique_id=None,
        data_updates=user_input,
    )
