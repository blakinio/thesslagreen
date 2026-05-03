"""Tests for config_flow helper functions that don't require HA."""

import asyncio

import pytest
from custom_components.thessla_green_modbus.config_flow import (
    ConfigFlow,
    _normalize_baud_rate,
    _normalize_parity,
    _normalize_stop_bits,
    _run_with_retry,
)
from custom_components.thessla_green_modbus.config_flow_device_validation import (
    _build_success_payload,
    _validate_scan_result,
)
from custom_components.thessla_green_modbus.config_flow_schema import (
    _build_serial_defaults_and_validators,
)
from custom_components.thessla_green_modbus.config_flow_steps import (
    build_reauth_form_defaults,
    extract_discovered_state,
    initialize_reauth_state,
    resolve_reauth_defaults,
    resolve_reauth_entry,
)
from custom_components.thessla_green_modbus.errors import CannotConnect
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException

# ---------------------------------------------------------------------------
# _normalize_baud_rate
# ---------------------------------------------------------------------------


def test_normalize_baud_rate_valid_string():
    assert _normalize_baud_rate("9600") == 9600


def test_normalize_baud_rate_valid_int():
    assert _normalize_baud_rate(115200) == 115200


def test_normalize_baud_rate_with_prefix():
    assert _normalize_baud_rate("modbus_baud_rate_19200") == 19200


def test_normalize_baud_rate_invalid_string():
    with pytest.raises(ValueError):
        _normalize_baud_rate("bad")


def test_normalize_baud_rate_zero():
    with pytest.raises(ValueError):
        _normalize_baud_rate(0)


def test_normalize_baud_rate_non_string_non_int():
    with pytest.raises(ValueError):
        _normalize_baud_rate(3.14)


# ---------------------------------------------------------------------------
# _normalize_parity
# ---------------------------------------------------------------------------


def test_normalize_parity_none_string():
    assert _normalize_parity("None") == "none"


def test_normalize_parity_even():
    assert _normalize_parity("even") == "even"


def test_normalize_parity_odd():
    assert _normalize_parity("ODD") == "odd"


def test_normalize_parity_with_prefix():
    assert _normalize_parity("modbus_parity_even") == "even"


def test_normalize_parity_invalid():
    with pytest.raises(ValueError):
        _normalize_parity("invalid")


def test_normalize_parity_none_value():
    with pytest.raises(ValueError):
        _normalize_parity(None)


# ---------------------------------------------------------------------------
# _normalize_stop_bits
# ---------------------------------------------------------------------------


def test_normalize_stop_bits_valid_string_1():
    assert _normalize_stop_bits("1") == 1


def test_normalize_stop_bits_valid_int_2():
    assert _normalize_stop_bits(2) == 2


def test_normalize_stop_bits_with_prefix():
    assert _normalize_stop_bits("modbus_stop_bits_2") == 2


def test_normalize_stop_bits_invalid_value():
    with pytest.raises(ValueError):
        _normalize_stop_bits("3")


def test_normalize_stop_bits_non_string_non_int():
    with pytest.raises(ValueError):
        _normalize_stop_bits(1.5)


def test_normalize_stop_bits_bad_string():
    with pytest.raises(ValueError):
        _normalize_stop_bits("bad")


# ---------------------------------------------------------------------------
# _run_with_retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_retry_cancelled_error_propagates():
    """CancelledError must not be swallowed by the retry loop."""

    async def failing():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await _run_with_retry(failing, retries=3, backoff=0)


@pytest.mark.asyncio
async def test_run_with_retry_timeout_exhausted():
    """After all retries, TimeoutError is re-raised."""
    call_count = 0

    async def failing():
        nonlocal call_count
        call_count += 1
        raise TimeoutError("boom")

    with pytest.raises(TimeoutError):
        await _run_with_retry(failing, retries=2, backoff=0)

    assert call_count == 2


@pytest.mark.asyncio
async def test_run_with_retry_modbus_io_success_on_second():
    """Succeeds on second attempt after ModbusIOException."""
    attempt = 0

    async def flaky():
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise ModbusIOException("transient")
        return "ok"

    result = await _run_with_retry(flaky, retries=2, backoff=0)
    assert result == "ok"
    assert attempt == 2


@pytest.mark.asyncio
async def test_run_with_retry_modbus_io_cancelled_request_raises_timeout():
    """ModbusIOException with 'cancelled' message converts to TimeoutError."""

    async def failing():
        raise ModbusIOException("request cancelled by something")

    with pytest.raises(TimeoutError):
        await _run_with_retry(failing, retries=3, backoff=0)


@pytest.mark.asyncio
async def test_run_with_retry_sync_func_returns_value():
    """Synchronous callables work (no await needed)."""

    def sync_fn():
        return 42

    result = await _run_with_retry(sync_fn, retries=1, backoff=0)
    assert result == 42


# ---------------------------------------------------------------------------
# _build_connection_schema with empty MODBUS_BAUD_RATES / MODBUS_PARITY / MODBUS_STOP_BITS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_connection_schema_empty_option_lists():
    """Cover the fallback branches when MODBUS_BAUD_RATES/PARITY/STOP_BITS are empty."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    original_baud = cf_mod.MODBUS_BAUD_RATES
    original_parity = cf_mod.MODBUS_PARITY
    original_stop_bits = cf_mod.MODBUS_STOP_BITS

    try:
        cf_mod.MODBUS_BAUD_RATES = []
        cf_mod.MODBUS_PARITY = []
        cf_mod.MODBUS_STOP_BITS = []

        flow = ConfigFlow()
        flow.hass = None
        schema = flow._build_connection_schema({})
        # Should not raise — just verifies the empty-list branches are reached
        assert schema is not None
    finally:
        cf_mod.MODBUS_BAUD_RATES = original_baud
        cf_mod.MODBUS_PARITY = original_parity
        cf_mod.MODBUS_STOP_BITS = original_stop_bits


@pytest.mark.asyncio
async def test_build_connection_schema_tcp_rtu_connection_default():
    """Cover connection_default = CONNECTION_TYPE_TCP_RTU branch (line 642)."""
    from custom_components.thessla_green_modbus.const import (
        CONF_CONNECTION_MODE,
        CONF_CONNECTION_TYPE,
        CONNECTION_MODE_TCP_RTU,
        CONNECTION_TYPE_TCP,
    )
    from homeassistant.const import CONF_PORT

    flow = ConfigFlow()
    flow.hass = None
    defaults = {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
        CONF_CONNECTION_MODE: CONNECTION_MODE_TCP_RTU,
        CONF_PORT: 502,
    }
    schema = flow._build_connection_schema(defaults)
    assert schema is not None


@pytest.mark.asyncio
async def test_build_connection_schema_empty_baud_rates_bad_baud_default():
    """Cover except (TypeError, ValueError) when int(baud_default) fails (lines 670-671)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    original_baud = cf_mod.MODBUS_BAUD_RATES
    try:
        cf_mod.MODBUS_BAUD_RATES = []
        flow = ConfigFlow()
        flow.hass = None
        schema = flow._build_connection_schema({"baud_rate": "invalid_baud"})
        assert schema is not None
    finally:
        cf_mod.MODBUS_BAUD_RATES = original_baud


def test_validate_scan_result_rejects_empty():
    with pytest.raises(CannotConnect) as err:
        _validate_scan_result({})
    assert err.value.args[0] == "invalid_format"


def test_build_success_payload_includes_title_and_scan_result():
    scan_result = {"device_info": {"model": "x"}}
    payload = _build_success_payload("Name", scan_result)
    assert payload["title"] == "Name"
    assert payload["device_info"] == {"model": "x"}
    assert payload["scan_result"] is scan_result


def test_build_serial_defaults_and_validators_without_option_lists():
    values = {"baud_rate": "invalid_baud", "parity": "Odd", "stop_bits": 2}
    resolved = _build_serial_defaults_and_validators(
        values,
        baud_options=[],
        parity_options=[],
        stop_bits_options=[],
    )
    assert resolved["baud_default"] == 9600
    assert resolved["parity_default"] == "Odd"
    assert resolved["stop_bits_default"] == "2"


# ---------------------------------------------------------------------------
# Additional coverage tests for config_flow utility functions
# ---------------------------------------------------------------------------


def test_vol_invalid_class():
    """VOL_INVALID should expose voluptuous.Invalid-like path/message behavior."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    err = cf_mod.VOL_INVALID("test message", path=["field"])
    assert err.error_message == "test message"


def test_extract_discovered_state_returns_dicts():
    """Helper should normalize missing keys to empty dicts."""
    device_info, scan_result = extract_discovered_state({"device_info": {"name": "x"}})
    assert device_info == {"name": "x"}
    assert scan_result == {}


def test_resolve_reauth_defaults_options_overridden_by_data():
    """Entry data should override conflicting option defaults."""
    defaults = resolve_reauth_defaults(
        {"host": "from_data", "slave_id": 3},
        {"host": "from_options", "deep_scan": True},
    )
    assert defaults == {"host": "from_data", "slave_id": 3, "deep_scan": True}


def test_resolve_reauth_entry_without_hass_returns_none():
    assert resolve_reauth_entry(None, {"entry_id": "x"}) is None


def test_initialize_reauth_state_initializes_from_entry():
    class Entry:
        entry_id = "entry-1"

    should_init, entry_id, defaults = initialize_reauth_state(
        active_entry_id=None,
        entry=Entry(),
        defaults={"host": "10.0.0.10"},
    )
    assert should_init is True
    assert entry_id == "entry-1"
    assert defaults == {"host": "10.0.0.10"}


def test_build_reauth_form_defaults_prefers_user_input():
    defaults = build_reauth_form_defaults(
        user_input={"host": "from_user"},
        existing_data={"host": "from_existing"},
    )
    assert defaults == {"host": "from_user"}


def test_build_reauth_form_defaults_falls_back_to_existing():
    defaults = build_reauth_form_defaults(
        user_input=None,
        existing_data={"host": "from_existing"},
    )
    assert defaults == {"host": "from_existing"}


def test_vol_invalid_no_path():
    """VOL_INVALID without explicit path should keep empty path."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    err = cf_mod.VOL_INVALID("error")
    assert err.path == []


def test_normalize_baud_rate_string_zero():
    """_normalize_baud_rate('0') → int 0 → <= 0 → ValueError (line 209)."""
    with pytest.raises(ValueError):
        _normalize_baud_rate("0")


def test_denormalize_option_none():
    """_denormalize_option with None returns None (line 249)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    result = cf_mod._denormalize_option("prefix_", None)
    assert result is None


def test_denormalize_option_already_prefixed():
    """_denormalize_option with domain-prefixed value returns it unchanged (line 251)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import DOMAIN

    val = f"{DOMAIN}.some_value"
    result = cf_mod._denormalize_option("prefix_", val)
    assert result == val


def test_looks_like_hostname_empty():
    """_looks_like_hostname with empty string returns False (line 258)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    assert cf_mod._looks_like_hostname("") is False


def test_looks_like_hostname_starts_with_dash():
    """_looks_like_hostname with leading dash returns False (line 264)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    assert cf_mod._looks_like_hostname("-invalid.host") is False


# ---------------------------------------------------------------------------
# Pass 16 — D2: _strip_translation_prefix with domain prefix (line 189)
# ---------------------------------------------------------------------------


def test_strip_translation_prefix_with_domain_prefix():
    """Value with domain prefix gets stripped (line 189)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import DOMAIN

    result = cf_mod._strip_translation_prefix(f"{DOMAIN}.some_value")
    assert result == "some_value"


# ---------------------------------------------------------------------------
# Pass 16 — D3: _normalize_parity non-string non-None (line 218)
# ---------------------------------------------------------------------------


def test_normalize_parity_non_string_non_none():
    """Non-string, non-None value is str()-converted then fails validation (line 218)."""
    with pytest.raises(ValueError):
        _normalize_parity(42)


# ---------------------------------------------------------------------------
# Pass 16 — D4: _caps_to_dict branches (lines 311, 322, 326, 330)
# ---------------------------------------------------------------------------


def test_caps_to_dict_dataclass_no_as_dict():
    """dataclass without as_dict uses dataclasses.asdict (line 322)."""
    import dataclasses

    import custom_components.thessla_green_modbus.config_flow as cf_mod

    @dataclasses.dataclass
    class Cap:
        has_feature: bool = True

    result = cf_mod._caps_to_dict(Cap())
    assert result["has_feature"] is True


def test_caps_to_dict_dict_with_set_value():
    """dict input with set value converts to sorted list (lines 326, 330)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    result = cf_mod._caps_to_dict({"a": 1, "b": {3, 1, 2}})
    assert result["a"] == 1
    assert result["b"] == [1, 2, 3]


def test_caps_to_dict_plain_object():
    """Object with __dict__ uses getattr fallback (line 311 else branch)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    class Obj:
        def __init__(self):
            self.y = 42

    result = cf_mod._caps_to_dict(Obj())
    assert result.get("y") == 42


def test_caps_to_dict_obj_with_as_dict():
    """Object with as_dict() method uses it (line 322 elif)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    class ObjWithAsDict:
        def as_dict(self):
            return {"x": 99}

    result = cf_mod._caps_to_dict(ObjWithAsDict())
    assert result["x"] == 99


# ---------------------------------------------------------------------------
# Pass 16 — D5: validate_input branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_with_optional_timeout_sync_function():
    """Sync function returns result without awaiting (line 311)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod

    result = await cf_mod._call_with_optional_timeout(lambda: 42, timeout=5.0)
    assert result == 42


# ---------------------------------------------------------------------------
# Pass 16 — lines 425-428: RTU validation success path
# ---------------------------------------------------------------------------
