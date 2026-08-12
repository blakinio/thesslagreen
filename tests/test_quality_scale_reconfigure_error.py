# mypy: ignore-errors
"""Cover the reconfigure validation and success edge paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_TCP,
)
from homeassistant.const import CONF_HOST, CONF_PORT


@pytest.mark.asyncio
async def test_reconfigure_validation_error_redisplays_form() -> None:
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

    with patch(
        "custom_components.thessla_green_modbus._config_flow._process_user_submission_impl",
        new=AsyncMock(return_value=(None, {"base": "cannot_connect"})),
    ):
        result = await flow.async_step_reconfigure(
            {CONF_HOST: "192.0.2.99", CONF_PORT: 502, CONF_SLAVE_ID: 10}
        )

    assert result == {"type": "form"}
    assert flow.async_show_form.call_args.kwargs["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_reconfigure_success_without_new_stable_id_keeps_existing_identity() -> None:
    entry = SimpleNamespace(
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 502,
            CONF_SLAVE_ID: 10,
        },
        unique_id="existing-id",
    )
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow._get_reconfigure_entry = MagicMock(return_value=entry)
    flow._build_stable_unique_id = MagicMock(return_value=None)
    flow.async_set_unique_id = AsyncMock()
    flow.async_update_and_abort = MagicMock(return_value={"type": "abort", "reason": "reconfigure_successful"})

    info = {"device_info": {"firmware": "4.85"}, "scan_result": {"register_count": 1}}
    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow._process_user_submission_impl",
            new=AsyncMock(return_value=(info, {})),
        ),
        patch(
            "custom_components.thessla_green_modbus._config_flow._extract_discovered_state_impl",
            return_value=(info["device_info"], info["scan_result"]),
        ),
    ):
        result = await flow.async_step_reconfigure(
            {CONF_HOST: "192.0.2.99", CONF_PORT: 502, CONF_SLAVE_ID: 10}
        )

    assert result == {"type": "abort", "reason": "reconfigure_successful"}
    flow.async_set_unique_id.assert_not_awaited()
    flow.async_update_and_abort.assert_called_once()
    assert flow.async_update_and_abort.call_args.kwargs["unique_id"] == "existing-id"
