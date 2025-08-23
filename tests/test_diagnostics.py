import copy
import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace, ModuleType
from unittest.mock import AsyncMock, patch
import sys

import pytest

# Stub registers module to avoid heavy imports during diagnostics import
registers_stub = ModuleType("custom_components.thessla_green_modbus.registers")
registers_stub.get_all_registers = lambda: []
registers_stub.get_registers_hash = lambda: "hash"
registers_stub.get_registers_by_function = lambda *args, **kwargs: []
registers_stub.group_reads = lambda *args, **kwargs: []
sys.modules["custom_components.thessla_green_modbus.registers"] = registers_stub
sys.modules.setdefault("voluptuous", ModuleType("voluptuous"))

from custom_components.thessla_green_modbus.diagnostics import (
    _redact_sensitive_data,
    async_get_config_entry_diagnostics,
)
from custom_components.thessla_green_modbus.scanner_core import DeviceCapabilities

DOMAIN = "thessla_green_modbus"


def test_redact_ipv4_and_ipv6():
    data = {
        "connection": {"host": "192.168.0.17"},
        "recent_errors": [{"message": "Error contacting 192.168.0.17 and 2001:db8::1"}],
    }

    redacted = _redact_sensitive_data(data)

    assert redacted["connection"]["host"] == "192.xxx.xxx.17"
    message = redacted["recent_errors"][0]["message"]
    assert "192.xxx.xxx.17" in message
    assert "2001:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:0001" in message


def test_redact_ipv6_connection():
    data = {"connection": {"host": "2001:db8::7334"}}

    redacted = _redact_sensitive_data(data)

    assert redacted["connection"]["host"] == ("2001:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:7334")


def test_original_diagnostics_unchanged():
    """Ensure the input diagnostics dict is not modified by redaction."""
    data = {
        "connection": {"host": "192.168.0.17"},
        "device_info": {"serial_number": "123456"},
    }

    original = copy.deepcopy(data)

    _redact_sensitive_data(data)

    assert data == original


@pytest.mark.asyncio
async def test_last_scan_in_diagnostics():
    """Ensure diagnostics include last_scan timestamp."""

    last_scan = datetime(2024, 1, 1, tzinfo=timezone.utc)

    class DummyCoordinator:
        def __init__(self) -> None:
            self.last_scan = last_scan
            self.device_scan_result = None
            self.data = {}
            self.device_info = {}
            self.available_registers = {}
            self.statistics = {}
            self.capabilities = SimpleNamespace(as_dict=lambda: {})

        def get_diagnostic_data(self):
            return {}

    coord = DummyCoordinator()
    entry = SimpleNamespace(entry_id="test")
    hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: coord}}, config=SimpleNamespace(language="en"))

    with patch(
        "custom_components.thessla_green_modbus.diagnostics.translation.async_get_translations",
        AsyncMock(return_value={}),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["last_scan"] == last_scan.isoformat()


@pytest.mark.asyncio
async def test_additional_diagnostic_fields():
    """Verify new diagnostic fields are included."""

    last_scan = datetime(2024, 1, 1, tzinfo=timezone.utc)

    class DummyCoordinator:
        def __init__(self) -> None:
            self.last_scan = last_scan
            self.device_scan_result = None
            self.data = {}
            self.device_info = {"firmware": "1.2.3"}
            self.available_registers = {
                "input_registers": {"a", "b"},
                "holding_registers": {"c"},
            }
            self.statistics = {"connection_errors": 2, "timeout_errors": 1}
            self.capabilities = SimpleNamespace(as_dict=lambda: {"fan": True})

        def get_diagnostic_data(self):
            return {}

    coord = DummyCoordinator()
    entry = SimpleNamespace(entry_id="test")
    hass = SimpleNamespace(
        data={DOMAIN: {entry.entry_id: coord}},
        config=SimpleNamespace(language="en"),
    )

    with patch(
        "custom_components.thessla_green_modbus.diagnostics.translation.async_get_translations",
        AsyncMock(return_value={}),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["firmware_version"] == "1.2.3"
    assert result["total_available_registers"] == 3
    assert result["error_statistics"] == {
        "connection_errors": 2,
        "timeout_errors": 1,
    }
    assert result["last_scan"] == last_scan.isoformat()


@pytest.mark.asyncio
async def test_unknown_registers_in_diagnostics():
    """Ensure diagnostics include skipped and unknown registers from scan."""

    last_scan = datetime(2024, 1, 1, tzinfo=timezone.utc)

    scan_result = {
        "unknown_registers": {"input_registers": {1: 99}},
        "failed_addresses": {
            "modbus_exceptions": {"input_registers": [2]},
            "invalid_values": {},
        },
    }

    class DummyCoordinator:
        def __init__(self) -> None:
            self.last_scan = last_scan
            self.device_scan_result = scan_result
            self.data = {}
            self.device_info = {}
            self.available_registers = {}
            self.statistics = {}
            self.capabilities = SimpleNamespace(as_dict=lambda: {"fan": True})
            self.unknown_registers = scan_result["unknown_registers"]

        def get_diagnostic_data(self):
            return {}

    coord = DummyCoordinator()
    entry = SimpleNamespace(entry_id="test")
    hass = SimpleNamespace(
        data={DOMAIN: {entry.entry_id: coord}},
        config=SimpleNamespace(language="en"),
    )

    with patch(
        "custom_components.thessla_green_modbus.diagnostics.translation.async_get_translations",
        AsyncMock(return_value={}),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["unknown_registers"] == scan_result["unknown_registers"]
    assert result["failed_addresses"] == scan_result["failed_addresses"]
    assert result["registers_hash"] == "hash"
    assert result["capabilities"] == {"fan": True}


@pytest.mark.asyncio
async def test_diagnostics_json_serializable():
    """Ensure diagnostics data is JSON serializable."""

    last_scan = datetime(2024, 1, 1, tzinfo=timezone.utc)

    class DummyCoordinator:
        def __init__(self) -> None:
            self.last_scan = last_scan
            self.device_scan_result = None
            self.data = {}
            self.device_info = {}
            self.available_registers = {}
            self.statistics = {}
            self.capabilities = DeviceCapabilities(
                temperature_sensors={"t1", "t2"},
                flow_sensors={"f1"},
            )

        def get_diagnostic_data(self):
            return {}

    coord = DummyCoordinator()
    entry = SimpleNamespace(entry_id="test")
    hass = SimpleNamespace(
        data={DOMAIN: {entry.entry_id: coord}},
        config=SimpleNamespace(language="en"),
    )

    with patch(
        "custom_components.thessla_green_modbus.diagnostics.translation.async_get_translations",
        AsyncMock(return_value={}),
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    serialized = json.dumps(result)
    assert isinstance(serialized, str)


@pytest.mark.asyncio
async def test_translation_failure_handled(caplog):
    """Ensure translation errors do not break diagnostics."""

    last_scan = datetime(2024, 1, 1, tzinfo=timezone.utc)

    class DummyCoordinator:
        def __init__(self) -> None:
            self.last_scan = last_scan
            self.device_scan_result = None
            self.data = {"e_fault": True}
            self.device_info = {}
            self.available_registers = {}
            self.statistics = {}
            self.capabilities = SimpleNamespace(as_dict=lambda: {})

        def get_diagnostic_data(self):
            return {}

    coord = DummyCoordinator()
    entry = SimpleNamespace(entry_id="test")
    hass = SimpleNamespace(
        data={DOMAIN: {entry.entry_id: coord}},
        config=SimpleNamespace(language="en"),
    )

    with patch(
        "custom_components.thessla_green_modbus.diagnostics.translation.async_get_translations",
        AsyncMock(side_effect=Exception("boom")),
    ):
        with caplog.at_level(logging.DEBUG):
            result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["active_errors"] == {"e_fault": "e_fault"}
    assert any("translation" in record.message.lower() for record in caplog.records)
