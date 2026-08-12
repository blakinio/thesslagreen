# mypy: ignore-errors
"""Close remaining helper and compatibility coverage branches without suppression."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus import const as const_module
from custom_components.thessla_green_modbus.mappings import _helpers as mapping_helpers
from custom_components.thessla_green_modbus.mappings import (
    _mapping_classification as classification,
)
from custom_components.thessla_green_modbus.registers import codec
from custom_components.thessla_green_modbus.scanner import capabilities_facade, io_runtime
from custom_components.thessla_green_modbus.transport import base as base_module
from custom_components.thessla_green_modbus.transport import rtu as rtu_module
from custom_components.thessla_green_modbus.transport import tcp as tcp_module
from pymodbus.exceptions import ConnectionException


def test_const_homeassistant_platform_fallback_is_complete() -> None:
    """The import fallback exposes every supported platform name."""
    real_import = __import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "homeassistant.const":
            raise ModuleNotFoundError("homeassistant.const unavailable")
        return real_import(name, globals, locals, fromlist, level)

    try:
        with patch("builtins.__import__", side_effect=blocked_import):
            importlib.reload(const_module)
            assert const_module.Platform.BINARY_SENSOR == "binary_sensor"
            assert const_module.Platform.BUTTON == "button"
            assert const_module.Platform.CLIMATE == "climate"
            assert const_module.Platform.FAN == "fan"
            assert const_module.Platform.NUMBER == "number"
            assert const_module.Platform.SELECT == "select"
            assert const_module.Platform.SENSOR == "sensor"
            assert const_module.Platform.SWITCH == "switch"
            assert const_module.Platform.TEXT == "text"
            assert const_module.Platform.TIME == "time"
    finally:
        importlib.reload(const_module)


def test_mapping_translation_key_fallbacks_are_fail_closed() -> None:
    """Missing or malformed translations return empty whitelists."""
    for side_effect in (OSError("missing"), TypeError("invalid")):
        mapping_helpers._number_translation_keys.cache_clear()
        with patch.object(mapping_helpers.Path, "open", side_effect=side_effect):
            assert mapping_helpers._number_translation_keys() == set()

        mapping_helpers._load_translation_keys.cache_clear()
        with patch.object(mapping_helpers.Path, "open", side_effect=side_effect):
            assert mapping_helpers._load_translation_keys() == {
                "binary_sensor": set(),
                "switch": set(),
                "select": set(),
            }

    mapping_helpers._number_translation_keys.cache_clear()
    mapping_helpers._load_translation_keys.cache_clear()


def test_mapping_classification_covers_all_whitelist_routes() -> None:
    """Enum and min/max routing fails closed unless a translated entity exists."""
    assert classification.classify_enum_mapping(
        "toggle", {0: "off", 1: "on"}, "RW", set(), set(), set()
    ) == (None, None)
    assert classification.classify_enum_mapping(
        "toggle", {0: "off", 1: "on"}, "R", set(), set(), set()
    ) == (None, None)
    assert classification.classify_enum_mapping(
        "mode", {0: "off", 1: "auto", 2: "boost"}, "RW", set(), set(), set()
    ) == (None, None)
    bucket, payload = classification.classify_enum_mapping(
        "mode", {0: "off", 1: "auto", 2: "boost"}, "R", set(), set(), set()
    )
    assert bucket == "sensor"
    assert payload["translation_key"] == "mode"

    common = dict(
        info_text="",
        unit=None,
        step=1,
        scale=1,
        switch_keys=set(),
        binary_keys=set(),
        select_keys=set(),
        number_keys=set(),
    )
    assert classification.classify_min_max_mapping(
        "missing", "RW", None, 1, **common
    ) == (None, None)
    assert classification.classify_min_max_mapping(
        "switch", "RW", 0, 1, **common
    ) == (None, None)
    assert classification.classify_min_max_mapping(
        "binary", "R", 0, 1, **common
    ) == (None, None)

    enum_common = dict(common)
    enum_common["info_text"] = "0 - off; 1 - low; 2 - high"
    assert classification.classify_min_max_mapping(
        "select", "RW", 0, 3, **enum_common
    ) == (None, None)

    assert classification.classify_min_max_mapping(
        "number", "RW", 0, 100, **common
    ) == (None, None)
    number_common = dict(common)
    number_common["number_keys"] = {"number"}
    bucket, payload = classification.classify_min_max_mapping(
        "number", "RW", 0, 100, **number_common
    )
    assert bucket == "number"
    assert payload["min"] == 0
    assert payload["max"] == 100
    assert classification.classify_min_max_mapping(
        "readonly", "R", 0, 100, **common
    ) == (None, None)


def test_register_codec_remaining_validation_paths() -> None:
    """Codec helpers cover string-key enums, flags, scaling, and invalid input."""
    assert codec.decode_enum_value(1, None) is None
    assert codec.decode_enum_value(1, {"1": "on"}) == "on"
    assert codec.decode_enum_value(2, {1: "on"}) is None
    assert codec.decode_bitmask_value(3, None) == []
    assert codec.decode_bitmask_value(5, {4: "four", 1: "one", 2: "two"}) == ["one", "four"]

    assert codec.encode_enum_value("7", None, "mode") == 7
    assert codec.encode_enum_value("on", {0: "off", 1: "on"}, "mode") == 1
    with pytest.raises(ValueError, match="Invalid enum value"):
        codec.encode_enum_value("bad", {0: "off"}, "mode")
    assert codec.encode_enum_value(1, {"1": "on"}, "mode") == 1
    with pytest.raises(ValueError, match="Invalid enum value"):
        codec.encode_enum_value(2, {0: "off", 1: "on"}, "mode")

    assert codec.apply_output_scaling(10, 0.5, 2) == 4
    assert codec.coerce_scaled_input(
        value=object(), raw_value=9, minimum=None, maximum=None,
        multiplier=None, resolution=None, name="value"
    ) == 9
    with pytest.raises(ValueError, match="below minimum"):
        codec.coerce_scaled_input(
            value=1, raw_value=1, minimum=2, maximum=None,
            multiplier=None, resolution=None, name="value"
        )
    with pytest.raises(ValueError, match="above maximum"):
        codec.coerce_scaled_input(
            value=9, raw_value=9, minimum=None, maximum=8,
            multiplier=None, resolution=None, name="value"
        )
    assert codec.coerce_scaled_input(
        value=5, raw_value=5, minimum=0, maximum=10,
        multiplier=0.5, resolution=2, name="value"
    ) == 8


def test_scanner_capabilities_facade_delegates_every_method() -> None:
    facade = capabilities_facade.ScannerCapabilitiesFacadeMixin()
    impl = capabilities_facade.scanner_capabilities
    caps = object()
    with (
        patch.object(impl, "is_valid_register_value", return_value=True) as valid,
        patch.object(impl, "analyze_capabilities", return_value=caps) as analyze,
        patch.object(impl, "filter_unsupported_addresses", return_value={1}) as filter_addrs,
        patch.object(impl, "log_invalid_value") as log_invalid,
        patch.object(impl, "mark_input_supported") as mark_input,
        patch.object(impl, "mark_holding_supported") as mark_holding,
        patch.object(impl, "mark_holding_unsupported") as holding_bad,
        patch.object(impl, "mark_input_unsupported") as input_bad,
    ):
        assert facade._is_valid_register_value("r", 1) is True
        assert facade._analyze_capabilities() is caps
        assert facade._filter_unsupported_addresses("holding", {1, 2}) == {1}
        facade._log_invalid_value("r", 99)
        facade._mark_input_supported(1)
        facade._mark_holding_supported(2)
        facade._mark_holding_unsupported(3, 4, 2)
        facade._mark_input_unsupported(5, 6, None)
    valid.assert_called_once_with(facade, "r", 1)
    analyze.assert_called_once_with(facade)
    filter_addrs.assert_called_once_with(facade, "holding", {1, 2})
    log_invalid.assert_called_once_with(facade, "r", 99)
    mark_input.assert_called_once_with(facade, 1)
    mark_holding.assert_called_once_with(facade, 2)
    holding_bad.assert_called_once_with(facade, 3, 4, 2)
    input_bad.assert_called_once_with(facade, 5, 6, None)


def test_scanner_io_runtime_attach_paths() -> None:
    """The optional pymodbus client attachment is both effective and fail-closed."""
    pymodbus = SimpleNamespace()
    client = object()
    with patch.object(io_runtime.importlib, "import_module", side_effect=[pymodbus, client]):
        io_runtime.attach_pymodbus_client_module()
    assert pymodbus.client is client

    with patch.object(io_runtime.importlib, "import_module", side_effect=ImportError("missing")):
        io_runtime.attach_pymodbus_client_module()


@pytest.mark.asyncio
async def test_scanner_io_runtime_sleep_executes_delay_adapter() -> None:
    observed = {}

    async def fake_sleep(*, calculate_backoff_delay, backoff, backoff_jitter, attempt, retry):
        observed["delay"] = calculate_backoff_delay(backoff, attempt, backoff_jitter)
        observed["retry"] = retry

    with patch.object(io_runtime._scanner_io_impl, "_sleep_retry_backoff_fn", new=fake_sleep):
        await io_runtime.sleep_retry_backoff(
            backoff=0.0, backoff_jitter=None, attempt=2, retry=3
        )
    assert observed == {"delay": 0.0, "retry": 3}


@pytest.mark.asyncio
async def test_base_transport_unexpected_error_marks_offline() -> None:
    transport = tcp_module.TcpModbusTransport(
        host="127.0.0.1", port=502, max_retries=1,
        base_backoff=0, max_backoff=0, timeout=1
    )

    async def bad_call():
        raise ValueError("bad")

    with pytest.raises(ValueError, match="bad"):
        await transport._execute(bad_call)
    assert transport.offline is True


@pytest.mark.asyncio
async def test_tcp_client_missing_and_rtu_over_tcp_unsupported() -> None:
    transport = tcp_module.TcpModbusTransport(
        host="127.0.0.1", port=502, max_retries=1,
        base_backoff=0, max_backoff=0, timeout=1
    )
    with pytest.raises(ConnectionException, match="client not initialized"):
        await transport._connect_client(endpoint="127.0.0.1:502")

    transport.connection_type = const_module.CONNECTION_TYPE_TCP_RTU
    with (
        patch.object(tcp_module, "get_rtu_framer", return_value=object()),
        patch.object(transport, "_build_tcp_client", side_effect=TypeError("unsupported")),
    ):
        with pytest.raises(ConnectionException, match="not supported"):
            await transport._connect()


def test_rtu_import_fallback_records_original_error() -> None:
    """Missing serial support leaves a useful runtime error instead of import failure."""
    real_import = __import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pymodbus.client" and "AsyncModbusSerialClient" in fromlist:
            raise ImportError("serial unavailable")
        return real_import(name, globals, locals, fromlist, level)

    try:
        with patch("builtins.__import__", side_effect=blocked_import):
            importlib.reload(rtu_module)
            assert rtu_module._AsyncModbusSerialClient is None
            assert isinstance(rtu_module.SERIAL_IMPORT_ERROR, ImportError)
    finally:
        importlib.reload(rtu_module)
