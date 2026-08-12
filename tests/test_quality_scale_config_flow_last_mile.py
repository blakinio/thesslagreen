# mypy: ignore-errors
"""Close the final config-flow quality-scale coverage branches."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus import _config_flow as flow_module
from custom_components.thessla_green_modbus._config_flow import ConfigFlow
from custom_components.thessla_green_modbus._config_flow.confirm import (
    build_confirmation_placeholders,
)
from custom_components.thessla_green_modbus._config_flow.device_validation import (
    _execute_validation_flow,
)
from custom_components.thessla_green_modbus._config_flow.entry import prepare_entry_payload
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONNECTION_MODE_TCP,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
)
from homeassistant.const import CONF_HOST, CONF_PORT


@dataclass
class _Caps:
    enabled: bool = False


@pytest.mark.asyncio
async def test_reconfigure_success_updates_stable_unique_id() -> None:
    entry = SimpleNamespace(
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 502,
            CONF_SLAVE_ID: 10,
        },
        unique_id="old-id",
    )
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow._get_reconfigure_entry = MagicMock(return_value=entry)
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_update_and_abort = MagicMock(return_value={"type": "abort"})

    info = {"device_info": {"serial_number": "123"}, "scan_result": {}}
    with (
        patch.object(
            flow_module,
            "_process_user_submission_impl",
            new=AsyncMock(return_value=(info, {})),
        ),
        patch.object(ConfigFlow, "_build_stable_unique_id", return_value="serial:123"),
    ):
        result = await flow.async_step_reconfigure(
            {CONF_HOST: "192.0.2.11", CONF_PORT: 1502, CONF_SLAVE_ID: 11}
        )

    assert result == {"type": "abort"}
    flow.async_set_unique_id.assert_awaited_once_with("serial:123")
    flow._abort_if_unique_id_configured.assert_called_once_with()
    flow.async_update_and_abort.assert_called_once()
    assert flow.async_update_and_abort.call_args.kwargs["unique_id"] == "serial:123"


@pytest.mark.asyncio
async def test_reconfigure_failed_submission_returns_errors() -> None:
    entry = SimpleNamespace(
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 502,
            CONF_SLAVE_ID: 10,
        },
        unique_id=None,
    )
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow._get_reconfigure_entry = MagicMock(return_value=entry)
    flow.async_show_form = MagicMock(return_value={"type": "form"})

    with patch.object(
        flow_module,
        "_process_user_submission_impl",
        new=AsyncMock(return_value=(None, {"base": "cannot_connect"})),
    ):
        result = await flow.async_step_reconfigure(
            {CONF_HOST: "192.0.2.99", CONF_PORT: 502, CONF_SLAVE_ID: 10}
        )

    assert result == {"type": "form"}
    assert flow.async_show_form.call_args.kwargs["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_dhcp_discovery_updates_host_and_routes_to_user() -> None:
    flow = ConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_step_user = AsyncMock(return_value={"type": "form"})
    discovery = SimpleNamespace(macaddress="aa:bb:cc:dd:ee:ff", ip="192.0.2.20")

    result = await flow.async_step_dhcp(discovery)

    assert result == {"type": "form"}
    flow.async_set_unique_id.assert_awaited_once_with("AA:BB:CC:DD:EE:FF")
    flow._abort_if_unique_id_configured.assert_called_once_with(
        updates={CONF_HOST: "192.0.2.20"}
    )
    assert flow._discovered_host == "192.0.2.20"
    flow.async_step_user.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_zeroconf_discovery_updates_host_and_routes_to_user() -> None:
    flow = ConfigFlow()
    flow._async_abort_entries_match = MagicMock()
    flow.async_step_user = AsyncMock(return_value={"type": "form"})
    discovery = SimpleNamespace(host="airpack.local")

    result = await flow.async_step_zeroconf(discovery)

    assert result == {"type": "form"}
    flow._async_abort_entries_match.assert_called_once_with({CONF_HOST: "airpack.local"})
    assert flow._discovered_host == "airpack.local"
    flow.async_step_user.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_reauth_without_initialization_or_input_redisplays_form() -> None:
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.context = {"entry_id": "entry-1"}
    entry = SimpleNamespace(entry_id="entry-1", data={CONF_HOST: "192.0.2.30"})
    flow._show_connection_form = MagicMock(return_value={"type": "form"})

    with (
        patch.object(flow_module, "_resolve_reauth_entry_impl", return_value=entry),
        patch.object(
            flow_module,
            "_resolve_reauth_form_state_impl",
            return_value=(False, "entry-1", {CONF_HOST: "192.0.2.30"}),
        ),
    ):
        result = await flow.async_step_reauth(None)

    assert result == {"type": "form"}
    flow._show_connection_form.assert_called_once_with(
        step_id="reauth",
        defaults={CONF_HOST: "192.0.2.30"},
        errors={},
    )


def test_async_get_options_flow_returns_bound_entry() -> None:
    entry = SimpleNamespace(data={}, options={})

    options = ConfigFlow.async_get_options_flow(entry)

    assert options.config_entry is entry


@pytest.mark.asyncio
async def test_full_scan_without_batch_failures_falls_back_to_deep_raw_summary() -> None:
    hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    scan_result = {
        "register_count": 1,
        "scan_mode": "full",
        "failed_addresses": {
            "batch_failures": {},
            "deep_scan_raw_failures": {"input_registers": [1, 2]},
            "expected_optional": {},
        },
        "capabilities": {},
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await build_confirmation_placeholders(
            hass=hass,
            data={
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                CONF_CONNECTION_MODE: CONNECTION_MODE_TCP,
                CONF_SLAVE_ID: 10,
                CONF_HOST: "192.0.2.40",
                CONF_PORT: 502,
            },
            device_info={},
            scan_result=scan_result,
            cap_cls=_Caps,
            caps_to_dict=Mock(return_value={}),
        )

    assert "2 unsupported raw ranges" in result["modbus_failed_summary"]


@pytest.mark.asyncio
async def test_execute_validation_flow_propagates_cancelled_error() -> None:
    with patch(
        "custom_components.thessla_green_modbus._config_flow.device_validation._create_scanner",
        new=AsyncMock(side_effect=asyncio.CancelledError()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _execute_validation_flow(
                hass=object(),
                params={"name": "Test"},
                scanner_cls=object,
                capabilities_cls=_Caps,
                run_with_retry=AsyncMock(),
                call_with_optional_timeout=AsyncMock(),
                process_scan_capabilities=Mock(),
                is_request_cancelled_error=Mock(return_value=False),
                classify_os_error=Mock(return_value="cannot_connect"),
                should_log_timeout_traceback=Mock(return_value=False),
                logger=Mock(),
                default_retry=1,
                config_flow_backoff=0.0,
                timeout_exceptions=(TimeoutError,),
            )


def test_prepare_entry_payload_serializes_dataclass_capabilities() -> None:
    entry_data, _ = prepare_entry_payload(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_SLAVE_ID: 10,
        },
        {
            "capabilities": _Caps(enabled=True),
            "available_registers": {},
            "device_info": {},
        },
        _Caps,
    )

    assert entry_data["capabilities"] == {"enabled": True}
