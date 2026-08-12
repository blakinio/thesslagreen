# mypy: ignore-errors
"""Close the remaining config-flow helper and orchestration coverage gaps."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus import _config_flow as flow_module
from custom_components.thessla_green_modbus._config_flow.confirm import (
    _build_capabilities_lists,
    _get_translations,
    _resolve_transport_labels,
    _summarize_address_dict,
    build_confirmation_placeholders,
)
from custom_components.thessla_green_modbus._config_flow.device_validation import (
    _map_validation_exception,
    _maybe_close_scanner,
    _raise_if_unmapped,
    _resolve_runtime_classes,
)
from custom_components.thessla_green_modbus._config_flow.entry import (
    _build_config_flow_scan_cache,
    prepare_entry_payload,
)
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
)
from custom_components.thessla_green_modbus.errors import CannotConnect, InvalidAuth
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException


@dataclass
class _Caps:
    enabled: bool = False
    disabled: bool = False
    count: int = 0


def test_config_flow_thin_wrappers_delegate() -> None:
    """Thin compatibility wrappers remain exercised as part of the flow module."""
    with (
        patch.object(flow_module, "_strip_translation_prefix_impl", return_value="even") as strip,
        patch.object(flow_module, "_normalize_baud_rate_impl", return_value=9600) as baud,
        patch.object(flow_module, "_normalize_parity_impl", return_value="even") as parity,
        patch.object(flow_module, "_normalize_stop_bits_impl", return_value=2) as stop,
        patch.object(flow_module, "_denormalize_option_impl", return_value="token") as denorm,
        patch.object(flow_module, "_looks_like_hostname_impl", return_value=True) as hostname,
        patch.object(flow_module, "_caps_to_dict_impl", return_value={"enabled": True}) as caps,
        patch.object(flow_module, "_normalize_connection_type_impl", return_value="tcp") as ctype,
        patch.object(flow_module, "_validate_slave_id_impl", return_value=10) as slave,
    ):
        assert flow_module._strip_translation_prefix("x") == "even"
        assert flow_module._normalize_baud_rate("x") == 9600
        assert flow_module._normalize_parity("x") == "even"
        assert flow_module._normalize_stop_bits("x") == 2
        assert flow_module._denormalize_option("prefix", 1) == "token"
        assert flow_module._looks_like_hostname("airpack.local") is True
        assert flow_module._caps_to_dict(object()) == {"enabled": True}
        data = {CONF_CONNECTION_TYPE: "tcp", CONF_SLAVE_ID: 10}
        assert flow_module._normalize_connection_type(data) == "tcp"
        assert flow_module._validate_slave_id(data) == 10

    strip.assert_called_once_with("x")
    baud.assert_called_once_with("x")
    parity.assert_called_once_with("x")
    stop.assert_called_once_with("x")
    denorm.assert_called_once_with("prefix", 1)
    hostname.assert_called_once_with("airpack.local")
    caps.assert_called_once()
    ctype.assert_called_once_with(data)
    slave.assert_called_once_with(data)


@pytest.mark.asyncio
async def test_config_flow_async_wrappers_delegate() -> None:
    retry_impl = AsyncMock(return_value="retried")
    timeout_impl = AsyncMock(return_value="timed")
    with (
        patch.object(flow_module, "_run_with_retry_impl", retry_impl),
        patch.object(flow_module, "_call_with_optional_timeout_impl", timeout_impl),
    ):
        callback = Mock()
        assert await flow_module._run_with_retry(callback, retries=2, backoff=0.5) == "retried"
        assert await flow_module._call_with_optional_timeout(callback, 3.0) == "timed"

    retry_impl.assert_awaited_once_with(callback, retries=2, backoff=0.5)
    timeout_impl.assert_awaited_once_with(callback, 3.0)


def test_capabilities_lists_fall_back_when_dataclass_rebuild_fails() -> None:
    source = _Caps(enabled=True)
    detected, not_detected = _build_capabilities_lists(
        _Caps,
        source,
        caps_to_dict=Mock(return_value={"unexpected": True}),
    )
    assert detected == []
    assert "Enabled" in not_detected
    assert "Disabled" in not_detected
    assert "Count" not in not_detected


def test_capabilities_lists_fall_back_when_dict_rebuild_fails() -> None:
    detected, not_detected = _build_capabilities_lists(
        _Caps,
        {"unexpected": True},
        caps_to_dict=Mock(),
    )
    assert detected == []
    assert "Enabled" in not_detected


def test_capabilities_lists_unknown_source_uses_defaults() -> None:
    detected, not_detected = _build_capabilities_lists(_Caps, object(), caps_to_dict=Mock())
    assert detected == []
    assert set(not_detected) == {"Enabled", "Disabled"}


def test_summarize_address_dict_exclusion_can_remove_entire_group() -> None:
    assert (
        _summarize_address_dict(
            {"holding_registers": [1, 2], "input_registers": []},
            exclude={"holding_registers": [1, 2]},
        )
        == "—"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [OSError("translations"), ValueError("translations"), HomeAssistantError("translations")],
)
async def test_get_translations_expected_errors_return_empty(error) -> None:
    hass = SimpleNamespace(config=SimpleNamespace(language="pl"))
    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(side_effect=error),
    ):
        assert await _get_translations(hass) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TypeError("bad api"), AttributeError("bad api"), RuntimeError("bad api")])
async def test_get_translations_unexpected_errors_return_empty(error) -> None:
    hass = SimpleNamespace(config=SimpleNamespace(language="pl"))
    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(side_effect=error),
    ):
        assert await _get_translations(hass) == {}


def test_resolve_transport_labels_covers_all_transport_modes() -> None:
    translations: dict[str, str] = {}

    rtu = _resolve_transport_labels(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            "host": "ignored",
            "port": 502,
        },
        translations,
    )
    assert rtu == ("ignored", "502", "/dev/ttyUSB0", "Modbus RTU", "RTU")

    tcp_rtu = _resolve_transport_labels(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_CONNECTION_MODE: CONNECTION_MODE_TCP_RTU,
            "host": "192.0.2.10",
            "port": 8899,
        },
        translations,
    )
    assert tcp_rtu == (
        "192.0.2.10",
        "8899",
        "192.0.2.10:8899",
        "Modbus TCP RTU",
        "TCP_RTU",
    )

    tcp = _resolve_transport_labels(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_CONNECTION_MODE: CONNECTION_MODE_TCP,
            "host": "192.0.2.11",
            "port": 502,
        },
        translations,
    )
    assert tcp[3:] == ("Modbus TCP", "TCP")


@pytest.mark.asyncio
async def test_confirmation_full_scan_and_deep_scan_fallback_notes() -> None:
    base = {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
        CONF_CONNECTION_MODE: CONNECTION_MODE_TCP,
        CONF_SLAVE_ID: 10,
        "host": "192.0.2.20",
        "port": 502,
    }
    hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    full_scan = {
        "register_count": 1,
        "scan_mode": "full",
        "failed_addresses": {
            "batch_failures": {"holding_registers": [1, 2]},
            "expected_optional": {},
        },
        "capabilities": {},
    }
    deep_scan = {
        "register_count": 1,
        "failed_addresses": {
            "deep_scan_raw_failures": {"input_registers": [1, 2, 3]},
            "expected_optional": {},
        },
        "capabilities": {},
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        full_result = await build_confirmation_placeholders(
            hass=hass,
            data=base,
            device_info={},
            scan_result=full_scan,
            cap_cls=_Caps,
            caps_to_dict=Mock(return_value={}),
        )
        deep_result = await build_confirmation_placeholders(
            hass=hass,
            data=base,
            device_info={},
            scan_result=deep_scan,
            cap_cls=_Caps,
            caps_to_dict=Mock(return_value={}),
        )

    assert "2 unsupported raw ranges" in full_result["modbus_failed_summary"]
    assert "3 unsupported raw ranges" in deep_result["modbus_failed_summary"]


@pytest.mark.asyncio
async def test_confirmation_excludes_expected_and_named_missing_addresses() -> None:
    hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    scan_result = {
        "register_count": 1,
        "missing_registers": {"holding_registers": {"missing_a": 2}},
        "failed_addresses": {
            "modbus_exceptions": {"holding_registers": [1, 2, 3]},
            "expected_optional": {"holding_registers": [1]},
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
                "host": "192.0.2.30",
                "port": 502,
            },
            device_info={},
            scan_result=scan_result,
            cap_cls=_Caps,
            caps_to_dict=Mock(return_value={}),
        )

    assert result["modbus_failed_summary"] == "holding_registers: 1"


@pytest.mark.asyncio
async def test_maybe_close_scanner_covers_none_sync_and_async_close() -> None:
    await _maybe_close_scanner(None)

    sync_scanner = SimpleNamespace(close=Mock(return_value=None))
    await _maybe_close_scanner(sync_scanner)
    sync_scanner.close.assert_called_once_with()

    async_scanner = SimpleNamespace(close=AsyncMock(return_value=None))
    await _maybe_close_scanner(async_scanner)
    async_scanner.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_resolve_runtime_classes_prefers_overrides_and_falls_back() -> None:
    module = SimpleNamespace(ThesslaGreenDeviceScanner="scanner", DeviceCapabilities="caps")
    loader = AsyncMock(return_value=module)

    assert await _resolve_runtime_classes(
        hass="hass",
        load_scanner_module=loader,
        scanner_cls_override="override-scanner",
        capabilities_cls_override="override-caps",
    ) == ("override-scanner", "override-caps")

    assert await _resolve_runtime_classes(
        hass="hass",
        load_scanner_module=loader,
        scanner_cls_override=None,
        capabilities_cls_override=None,
    ) == ("scanner", "caps")


def _map_error(error: BaseException, **overrides) -> BaseException:
    kwargs = {
        "is_request_cancelled_error": Mock(return_value=False),
        "classify_os_error": Mock(return_value="cannot_connect"),
        "should_log_timeout_traceback": Mock(return_value=False),
        "logger": Mock(),
        "timeout_exceptions": (TimeoutError,),
    }
    kwargs.update(overrides)
    return _map_validation_exception(error, **kwargs)


def test_validation_exception_mapping_connection_and_cancelled_io() -> None:
    assert isinstance(_map_error(ConnectionException("down")), CannotConnect)
    cancelled = _map_error(
        ModbusIOException("cancelled"),
        is_request_cancelled_error=Mock(return_value=True),
    )
    assert isinstance(cancelled, CannotConnect)
    assert str(cancelled) == "timeout"


def test_validation_exception_mapping_io_timeout_and_auth() -> None:
    io_error = _map_error(ModbusIOException("short frame"))
    assert isinstance(io_error, CannotConnect)
    assert str(io_error) == "io_error"

    timeout = _map_error(
        TimeoutError("slow"),
        should_log_timeout_traceback=Mock(return_value=True),
    )
    assert isinstance(timeout, CannotConnect)
    assert str(timeout) == "timeout"

    auth = _map_error(ModbusException("authentication failed"))
    assert isinstance(auth, InvalidAuth)
    regular = _map_error(ModbusException("illegal address"))
    assert isinstance(regular, CannotConnect)
    assert str(regular) == "modbus_error"


def test_validation_exception_mapping_attribute_os_and_generic() -> None:
    missing = _map_error(AttributeError("verify_connection"))
    assert isinstance(missing, CannotConnect)
    assert str(missing) == "missing_method"

    for reason in ("dns_failure", "connection_refused", "cannot_connect"):
        mapped = _map_error(
            OSError("network"),
            classify_os_error=Mock(return_value=reason),
        )
        assert isinstance(mapped, CannotConnect)
        assert str(mapped) == reason

    for error in (ValueError("bad"), TypeError("bad"), RuntimeError("bad"), ImportError("bad")):
        mapped = _map_error(error)
        assert isinstance(mapped, CannotConnect)
        assert str(mapped) == "cannot_connect"


def test_validation_exception_mapping_passthrough_and_raise_helper() -> None:
    original = KeyError("unknown")
    assert _map_error(original) is original
    with pytest.raises(KeyError):
        _raise_if_unmapped(original, original)

    mapped = CannotConnect("mapped")
    with pytest.raises(CannotConnect, match="mapped"):
        _raise_if_unmapped(mapped, original)


def test_entry_scan_cache_filters_invalid_groups_and_handles_capability_shapes() -> None:
    assert _build_config_flow_scan_cache({}, _Caps) is None
    assert _build_config_flow_scan_cache({"available_registers": {"holding": "bad"}}, _Caps) is None

    scan = {
        "available_registers": {"holding": {"b", "a"}, "ignored": "bad"},
        "device_info": {"firmware": "4.85"},
        "capabilities": _Caps(enabled=True),
        "register_count": 2,
    }
    cached = _build_config_flow_scan_cache(scan, _Caps)
    assert cached is not None
    assert cached["available_registers"] == {"holding": ["a", "b"]}
    assert cached["capabilities"]["enabled"] is True
    assert cached["firmware"] == "4.85"

    scan["capabilities"] = {"enabled": True}
    assert _build_config_flow_scan_cache(scan, _Caps)["capabilities"] == {"enabled": True}
    scan["capabilities"] = object()
    assert _build_config_flow_scan_cache(scan, _Caps)["capabilities"] == {}


def test_prepare_entry_payload_capability_fallback_and_rtu_optional_endpoint() -> None:
    data = {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
        CONF_SLAVE_ID: 10,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        "host": "legacy-host",
        "port": 8899,
    }
    scan = {
        "capabilities": {"unexpected": True},
        "available_registers": {"holding_registers": ["mode"]},
        "device_info": {},
    }

    entry_data, options = prepare_entry_payload(data, scan, _Caps)

    assert entry_data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_RTU
    assert entry_data["host"] == "legacy-host"
    assert entry_data["port"] == 8899
    assert entry_data["capabilities"] == {"enabled": False, "disabled": False, "count": 0}
    assert "config_flow_scan_cache" in options


def test_prepare_entry_payload_rtu_without_legacy_endpoint_omits_host_and_port() -> None:
    entry_data, _ = prepare_entry_payload(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
            CONF_SLAVE_ID: 10,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
        {"capabilities": None},
        _Caps,
    )
    assert "host" not in entry_data
    assert "port" not in entry_data
