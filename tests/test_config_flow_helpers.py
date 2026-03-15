"""Tests for config_flow helper functions that don't require HA."""

# ruff: noqa: E402

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

# Stub loader module to avoid heavy imports during tests
_loader_stub = SimpleNamespace(
    plan_group_reads=lambda *args, **kwargs: [],
    get_registers_by_function=lambda *args, **kwargs: [],
    get_all_registers=lambda *args, **kwargs: [],
    registers_sha256=lambda *args, **kwargs: "",
    load_registers=lambda *args, **kwargs: [],
    _REGISTERS_PATH=Path("dummy"),
)
sys.modules.setdefault(
    "custom_components.thessla_green_modbus.registers.loader",
    _loader_stub,
)
_network_module = SimpleNamespace(
    is_host_valid=lambda host: bool(host)
    and " " not in host
    and not host.replace(".", "").isdigit()
    and "." in host,
)
sys.modules.setdefault("homeassistant.util", SimpleNamespace(network=_network_module))
sys.modules.setdefault("homeassistant.util.network", _network_module)

_registers_module = ModuleType("custom_components.thessla_green_modbus.registers")
_registers_module.__path__ = []  # type: ignore[attr-defined]
_registers_module.get_registers_by_function = lambda *args, **kwargs: []  # type: ignore[attr-defined]
_registers_module.get_all_registers = lambda *args, **kwargs: []  # type: ignore[attr-defined]
_registers_module.registers_sha256 = lambda *args, **kwargs: ""  # type: ignore[attr-defined]
_registers_module.plan_group_reads = lambda *args, **kwargs: []  # type: ignore[attr-defined]
sys.modules.setdefault("custom_components.thessla_green_modbus.registers", _registers_module)
_loader_module = ModuleType("custom_components.thessla_green_modbus.registers.loader")
_loader_module.get_registers_by_function = lambda *args, **kwargs: []  # type: ignore[attr-defined]
_loader_module.load_registers = lambda *args, **kwargs: []  # type: ignore[attr-defined]
_loader_module.get_all_registers = lambda *args, **kwargs: []  # type: ignore[attr-defined]
_loader_module.registers_sha256 = lambda *args, **kwargs: ""  # type: ignore[attr-defined]
_loader_module._REGISTERS_PATH = Path("dummy")  # type: ignore[attr-defined]
sys.modules.setdefault(
    "custom_components.thessla_green_modbus.registers.loader", _loader_module
)

from custom_components.thessla_green_modbus.config_flow import (  # noqa: E402
    ConfigFlow,
    _normalize_baud_rate,
    _normalize_parity,
    _normalize_stop_bits,
    _run_with_retry,
)
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException


pytestmark = pytest.mark.asyncio


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


async def test_run_with_retry_cancelled_error_propagates():
    """CancelledError must not be swallowed by the retry loop."""

    async def failing():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await _run_with_retry(failing, retries=3, backoff=0)


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


async def test_run_with_retry_modbus_io_cancelled_request_raises_timeout():
    """ModbusIOException with 'cancelled' message converts to TimeoutError."""

    async def failing():
        raise ModbusIOException("request cancelled by something")

    with pytest.raises(TimeoutError):
        await _run_with_retry(failing, retries=3, backoff=0)


async def test_run_with_retry_sync_func_returns_value():
    """Synchronous callables work (no await needed)."""

    def sync_fn():
        return 42

    result = await _run_with_retry(sync_fn, retries=1, backoff=0)
    assert result == 42


# ---------------------------------------------------------------------------
# _build_connection_schema with empty MODBUS_BAUD_RATES / MODBUS_PARITY / MODBUS_STOP_BITS
# ---------------------------------------------------------------------------


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


async def test_build_connection_schema_tcp_rtu_connection_default():
    """Cover connection_default = CONNECTION_TYPE_TCP_RTU branch (line 642)."""
    from custom_components.thessla_green_modbus.const import (
        CONNECTION_TYPE_TCP,
        CONNECTION_MODE_TCP_RTU,
        CONF_CONNECTION_TYPE,
        CONF_CONNECTION_MODE,
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
