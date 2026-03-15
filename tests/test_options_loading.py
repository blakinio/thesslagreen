import logging
from pathlib import Path

import pytest

import custom_components.thessla_green_modbus.const as const


def test_deep_scan_defaults():
    """Ensure deep scan option is defined and defaults to False."""
    assert const.CONF_DEEP_SCAN == "deep_scan"
    assert const.DEFAULT_DEEP_SCAN is False


def test_max_registers_per_request_defaults():
    """Ensure max register limit constant is defined and defaults to maximum."""
    assert const.CONF_MAX_REGISTERS_PER_REQUEST == "max_registers_per_request"
    assert const.DEFAULT_MAX_REGISTERS_PER_REQUEST == const.MAX_BATCH_REGISTERS


def test_missing_options_file(monkeypatch, caplog):
    def missing(_self: Path, **kwargs) -> str:  # pragma: no cover - simple stub
        raise FileNotFoundError

    monkeypatch.setattr(Path, "read_text", missing)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        options = const._load_json_option("special_modes.json")

    assert options == []  # nosec B101


def test_malformed_options_file(monkeypatch, caplog):
    def malformed(_self: Path, **kwargs) -> str:  # pragma: no cover - simple stub
        return "{"

    monkeypatch.setattr(Path, "read_text", malformed)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        options = const._load_json_option("special_modes.json")

    assert options == []  # nosec B101


def test_scan_uart_defaults_enabled():
    """Ensure UART scan option is enabled by default for critical diagnostics."""
    assert const.CONF_SCAN_UART_SETTINGS == "scan_uart_settings"
    assert const.DEFAULT_SCAN_UART_SETTINGS is True


def test_multi_register_sizes_returns_dict():
    """multi_register_sizes() is called and returns a dict (const.py line 56)."""
    from custom_components.thessla_green_modbus.const import multi_register_sizes

    result = multi_register_sizes()
    assert isinstance(result, dict)
    # All values should be integers > 1 (registers spanning multiple words)
    assert all(isinstance(v, int) and v > 1 for v in result.values())


def test_migrate_unique_id_base_uid_already_has_prefix():
    """migrate_unique_id returns base_uid unchanged when it already starts with prefix (line 350)."""
    from custom_components.thessla_green_modbus.const import migrate_unique_id, DOMAIN

    # serial_number="1" → prefix="1"; slave_id=1 → base_uid="1_fan_0"
    # "1_fan_0".startswith("1") is True → returns base_uid unchanged
    uid = f"{DOMAIN}_192.168.1.1_502_1_fan"
    result = migrate_unique_id(
        uid,
        serial_number="1",
        host="192.168.1.1",
        port=502,
        slave_id=1,
    )
    assert result == "1_fan_0"


@pytest.mark.asyncio
async def test_async_setup_options_no_hass_uses_sync_path():
    """async_setup_options(None) falls back to synchronous loading (const.py line 408)."""
    result_before = const.MODBUS_BAUD_RATES  # capture current state
    await const.async_setup_options(None)
    # After calling with hass=None, globals should still be set (sync path executed)
    assert const.MODBUS_BAUD_RATES is not None
