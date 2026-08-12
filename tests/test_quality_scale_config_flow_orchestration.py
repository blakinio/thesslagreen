# mypy: ignore-errors
"""Exercise the remaining config-flow orchestration branches."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus._config_flow.confirm import (
    build_confirmation_placeholders,
)
from custom_components.thessla_green_modbus._config_flow.device_validation import (
    _execute_validation_flow,
)
from custom_components.thessla_green_modbus._config_flow.entry import prepare_entry_payload
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_SLAVE_ID,
    CONNECTION_MODE_TCP,
    CONNECTION_TYPE_TCP,
)
from homeassistant.const import CONF_HOST, CONF_PORT


@dataclass
class _Caps:
    enabled: bool = False


@pytest.mark.asyncio
async def test_reconfigure_updates_stable_serial_identity() -> None:
    entry = SimpleNamespace(
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 502,
            CONF_SLAVE_ID: 10,
        },
        unique_id="serial:old",
    )
    user_input = {CONF_HOST: "192.0.2.11", CONF_PORT: 502, CONF_SLAVE_ID: 10}
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow._get_reconfigure_entry = Mock(return_value=entry)
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
    flow.async_update_and_abort = Mock(return_value={"type": "abort"})

    with patch(
        "custom_components.thessla_green_modbus._config_flow._process_user_submission_impl",
        new=AsyncMock(
            return_value=(
                {"device_info": {"serial_number": " AP4-NEW "}, "scan_result": {}},
                {},
            )
        ),
    ):
        result = await flow.async_step_reconfigure(user_input)

    assert result == {"type": "abort"}
    flow.async_set_unique_id.assert_awaited_once_with("serial:ap4-new")
    flow._abort_if_unique_id_configured.assert_called_once_with()
    flow.async_update_and_abort.assert_called_once_with(
        entry,
        unique_id="serial:ap4-new",
        data_updates=user_input,
    )


@pytest.mark.asyncio
async def test_dhcp_discovery_applies_mac_identity_and_host() -> None:
    flow = ConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
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
async def test_zeroconf_discovery_matches_host_and_forwards_to_user_step() -> None:
    flow = ConfigFlow()
    flow._async_abort_entries_match = Mock()
    flow.async_step_user = AsyncMock(return_value={"type": "form"})
    discovery = SimpleNamespace(host="airpack.local")

    result = await flow.async_step_zeroconf(discovery)

    assert result == {"type": "form"}
    flow._async_abort_entries_match.assert_called_once_with({CONF_HOST: "airpack.local"})
    assert flow._discovered_host == "airpack.local"
    flow.async_step_user.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_reauth_initialized_state_with_no_input_renders_form() -> None:
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    flow._tg_flow_reauth_entry_id = "entry-1"
    flow._tg_flow_reauth_existing_data = {CONF_HOST: "192.0.2.30"}
    flow._show_connection_form = Mock(return_value={"type": "form"})
    defaults = {CONF_HOST: "192.0.2.30"}

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow._resolve_reauth_entry_impl",
            return_value=SimpleNamespace(entry_id="entry-1"),
        ),
        patch(
            "custom_components.thessla_green_modbus._config_flow._resolve_reauth_form_state_impl",
            return_value=(False, "entry-1", defaults),
        ),
    ):
        result = await flow.async_step_reauth(None)

    assert result == {"type": "form"}
    flow._show_connection_form.assert_called_once_with(
        step_id="reauth", defaults=defaults, errors={}
    )


def test_options_flow_factory_returns_bound_entry() -> None:
    entry = SimpleNamespace(data={}, options={})
    options_flow = ConfigFlow.async_get_options_flow(entry)
    assert options_flow.config_entry is entry


@pytest.mark.asyncio
async def test_full_scan_without_batch_failures_falls_through_to_deep_raw_summary() -> None:
    hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    scan_result = {
        "register_count": 1,
        "scan_mode": "full",
        "failed_addresses": {
            "batch_failures": {},
            "deep_scan_raw_failures": {"input_registers": [7]},
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

    assert "1 unsupported raw ranges" in result["modbus_failed_summary"]


@pytest.mark.asyncio
async def test_execute_validation_flow_propagates_task_cancellation() -> None:
    run_with_retry = AsyncMock(side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await _execute_validation_flow(
            hass=object(),
            params={},
            scanner_cls=object(),
            capabilities_cls=_Caps,
            run_with_retry=run_with_retry,
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


def test_prepare_entry_payload_accepts_capability_dataclass_directly() -> None:
    entry_data, options = prepare_entry_payload(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_CONNECTION_MODE: CONNECTION_MODE_TCP,
            CONF_SLAVE_ID: 10,
            CONF_HOST: "192.0.2.50",
            CONF_PORT: 502,
        },
        {
            "capabilities": _Caps(enabled=True),
            "available_registers": {"holding_registers": ["mode"]},
            "device_info": {},
            "register_count": 1,
        },
        _Caps,
    )

    assert entry_data["capabilities"] == {"enabled": True}
    assert "config_flow_scan_cache" in options
