"""Focused behavioral coverage for config-flow helper branches."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol
from custom_components.thessla_green_modbus._config_flow.errors import classify_os_error
from custom_components.thessla_green_modbus._config_flow.options_form import (
    build_transport_description,
)
from custom_components.thessla_green_modbus._config_flow.reauth_confirm import (
    apply_reauth_update,
)
from custom_components.thessla_green_modbus._config_flow.runtime import run_with_retry
from custom_components.thessla_green_modbus._config_flow.schema import (
    _build_serial_defaults_and_validators,
    _option_default,
)
from custom_components.thessla_green_modbus._config_flow.steps import resolve_reauth_entry
from custom_components.thessla_green_modbus._config_flow.validation import (
    process_scan_capabilities,
    validate_tcp_config,
)
from custom_components.thessla_green_modbus.const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_PARITY,
    CONF_STOP_BITS,
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DOMAIN,
)
from custom_components.thessla_green_modbus.errors import CannotConnect


def _transport_values() -> dict[str, object]:
    return {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
        CONF_CONNECTION_MODE: None,
        "entry_port": 502,
        "entry_serial_port": "",
        "entry_baud_rate": 9600,
        "entry_parity": "none",
        "entry_stop_bits": 1,
    }


def test_classify_os_error_connection_refused() -> None:
    """Connection-refused errors have their dedicated config-flow reason."""
    assert classify_os_error(ConnectionRefusedError()) == "connection_refused"


def test_classify_os_error_generic() -> None:
    """Generic OS errors use the conservative connection failure reason."""
    assert classify_os_error(OSError()) == "cannot_connect"


def test_build_transport_description_rtu() -> None:
    """RTU transport description includes normalized serial details."""
    values = _transport_values()
    with patch(
        "custom_components.thessla_green_modbus._config_flow.options_form.resolve_connection_settings",
        return_value=(CONNECTION_TYPE_RTU, None),
    ):
        label, details = build_transport_description(values)

    assert label == "Modbus RTU"
    assert details == " (port: n/a, baud: 9600, parity: none, stop bits: 1)"


def test_build_transport_description_tcp_rtu() -> None:
    """TCP-RTU mode receives its explicit transport label."""
    values = _transport_values()
    with patch(
        "custom_components.thessla_green_modbus._config_flow.options_form.resolve_connection_settings",
        return_value=(CONNECTION_TYPE_TCP, CONNECTION_MODE_TCP_RTU),
    ):
        assert build_transport_description(values) == ("Modbus TCP RTU", "")


def test_build_transport_description_auto() -> None:
    """Auto TCP mode is distinguished in the options-flow description."""
    values = _transport_values()
    with patch(
        "custom_components.thessla_green_modbus._config_flow.options_form.resolve_connection_settings",
        return_value=(CONNECTION_TYPE_TCP, CONNECTION_MODE_AUTO),
    ):
        assert build_transport_description(values) == ("Modbus TCP (Auto)", "")


def test_build_transport_description_plain_tcp() -> None:
    """Plain TCP mode retains the default transport label."""
    values = _transport_values()
    with patch(
        "custom_components.thessla_green_modbus._config_flow.options_form.resolve_connection_settings",
        return_value=(CONNECTION_TYPE_TCP, None),
    ):
        assert build_transport_description(values) == ("Modbus TCP", "")


def test_option_default_prefers_matching_translation_token() -> None:
    """Schema defaults retain a reviewed option when its token is available."""
    token = f"{DOMAIN}.modbus_baud_rate_9600"
    assert _option_default("modbus_baud_rate_", [token], 9600, 19200) == token


def test_option_default_falls_back_to_first_available_option() -> None:
    """Schema defaults select the first valid option when the current value is absent."""
    token = f"{DOMAIN}.modbus_baud_rate_9600"
    assert _option_default("modbus_baud_rate_", [token], 19200, 38400) == token


def test_serial_defaults_use_nonempty_selector_validators() -> None:
    """Non-empty serial selector lists produce token validators and defaults."""
    baud = f"{DOMAIN}.modbus_baud_rate_9600"
    parity = f"{DOMAIN}.modbus_parity_even"
    stop_bits = f"{DOMAIN}.modbus_stop_bits_1"

    result = _build_serial_defaults_and_validators(
        {
            CONF_BAUD_RATE: 9600,
            CONF_PARITY: "even",
            CONF_STOP_BITS: 1,
        },
        baud_options=[baud],
        parity_options=[parity],
        stop_bits_options=[stop_bits],
    )

    assert result["baud_default"] == baud
    assert result["parity_default"] == parity
    assert result["stop_bits_default"] == stop_bits
    assert result["baud_validator"](baud) == baud
    assert result["parity_validator"](parity) == parity
    assert result["stop_bits_validator"](stop_bits) == stop_bits


def test_validate_tcp_config_rejects_hostname_rejected_by_ha() -> None:
    """A hostname-shaped value must still pass Home Assistant host validation."""
    data = {"host": "airpack.local", "port": 502}
    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validation.is_host_valid",
            return_value=False,
        ),
        pytest.raises(vol.Invalid),
    ):
        validate_tcp_config(data, looks_like_hostname=lambda _host: True)


def test_process_scan_capabilities_maps_serializer_failure() -> None:
    """Dataclass serialization failures become a stable config-flow error."""

    @dataclass
    class Caps:
        enabled: bool = True

    with pytest.raises(CannotConnect):
        process_scan_capabilities(
            {"capabilities": Caps()},
            capabilities_cls=Caps,
            caps_to_dict=Mock(side_effect=TypeError("bad capabilities")),
            logger=Mock(),
        )


def test_process_scan_capabilities_accepts_foreign_dataclass() -> None:
    """A serializable dataclass need not be the active capabilities class."""

    @dataclass
    class ForeignCaps:
        enabled: bool = True

    @dataclass
    class ActiveCaps:
        enabled: bool = False

    assert process_scan_capabilities(
        {"capabilities": ForeignCaps()},
        capabilities_cls=ActiveCaps,
        caps_to_dict=Mock(return_value={"enabled": True}),
        logger=Mock(),
    ) == {"enabled": True}


def test_process_scan_capabilities_rejects_missing_required_fields() -> None:
    """Capabilities of the active dataclass type must include every public field."""

    @dataclass
    class Caps:
        enabled: bool = True

    logger = Mock()
    with pytest.raises(CannotConnect):
        process_scan_capabilities(
            {"capabilities": Caps()},
            capabilities_cls=Caps,
            caps_to_dict=Mock(return_value={}),
            logger=logger,
        )
    logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_apply_reauth_update_without_hass_fails_safely() -> None:
    """Reauth cannot mutate an entry without a Home Assistant context."""
    logger = Mock()

    result = await apply_reauth_update(
        hass=None,
        reauth_entry_id="entry-1",
        prepare_entry_payload=Mock(),
        capabilities_cls=object,
        logger=logger,
    )

    assert result == "reauth_failed"
    logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_apply_reauth_update_without_entry_id_fails_safely() -> None:
    """Reauth requires an explicit entry id before any mutation."""
    logger = Mock()
    hass = SimpleNamespace(config_entries=Mock())

    result = await apply_reauth_update(
        hass=hass,
        reauth_entry_id=None,
        prepare_entry_payload=Mock(),
        capabilities_cls=object,
        logger=logger,
    )

    assert result == "reauth_entry_missing"
    logger.error.assert_called_once()
    hass.config_entries.async_get_entry.assert_not_called()


@pytest.mark.asyncio
async def test_apply_reauth_update_accepts_nonawaitable_reload_result() -> None:
    """Reauth preserves existing options when reload returns synchronously."""
    entry = SimpleNamespace(entry_id="entry-1", options={"keep": True, "replace": "old"})
    manager = SimpleNamespace(
        async_get_entry=Mock(return_value=entry),
        async_update_entry=Mock(),
        async_reload=Mock(return_value=True),
    )
    hass = SimpleNamespace(config_entries=manager)
    prepare = Mock(return_value=({"host": "192.0.2.10"}, {"replace": "new"}))

    result = await apply_reauth_update(
        hass=hass,
        reauth_entry_id=entry.entry_id,
        prepare_entry_payload=prepare,
        capabilities_cls=object,
        logger=Mock(),
    )

    assert result == "reauth_successful"
    manager.async_update_entry.assert_called_once_with(
        entry,
        data={"host": "192.0.2.10"},
        options={"keep": True, "replace": "new"},
    )
    manager.async_reload.assert_called_once_with(entry.entry_id)


@pytest.mark.asyncio
async def test_run_with_retry_zero_retries_raises_guard_error() -> None:
    """A zero-attempt retry request reaches the defensive terminal guard."""
    with pytest.raises(RuntimeError, match="Retry wrapper failed without raising"):
        await run_with_retry(Mock(), retries=0, backoff=0)


def test_resolve_reauth_entry_without_context_entry_id_returns_none() -> None:
    """Missing flow context entry id must not query the config-entry registry."""
    hass = SimpleNamespace(config_entries=Mock())

    assert resolve_reauth_entry(hass, {}) is None
    hass.config_entries.async_get_entry.assert_not_called()
