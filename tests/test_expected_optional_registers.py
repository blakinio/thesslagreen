"""Tests for expected-optional register classification and config-flow exclusion."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus._config_flow.confirm import (
    _summarize_address_dict,
)
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from custom_components.thessla_green_modbus.const import KNOWN_MISSING_CLASSIFICATION
from custom_components.thessla_green_modbus.scanner.scan_runtime import (
    _collect_expected_optional_addresses,
)
from homeassistant.const import CONF_HOST, CONF_PORT

_N_A = "—"


class _FakeScanner:
    """Minimal scanner stub for _collect_expected_optional_addresses tests."""

    def __init__(
        self,
        *,
        failed: dict[str, set[int]] | None = None,
        unsupported_input_ranges: dict[tuple[int, int], int] | None = None,
    ):
        self.failed_addresses = {
            "modbus_exceptions": failed or {},
            "invalid_values": {},
        }
        self._unsupported_input_ranges = unsupported_input_ranges or {}


class TestCollectExpectedOptionalAddresses:
    """Tests for _collect_expected_optional_addresses."""

    def test_no_failed_input_registers(self):
        scanner = _FakeScanner()
        assert _collect_expected_optional_addresses(scanner) == {}

    def test_firmware_range_code2_below_15(self):
        scanner = _FakeScanner(
            failed={"input_registers": {4}},
            unsupported_input_ranges={(4, 4): 2},
        )
        result = _collect_expected_optional_addresses(scanner)
        assert result == {"input_registers": [4]}

    def test_firmware_range_code2_spanning_0_to_15(self):
        scanner = _FakeScanner(
            failed={"input_registers": {4, 5, 6, 7}},
            unsupported_input_ranges={(4, 15): 2},
        )
        result = _collect_expected_optional_addresses(scanner)
        assert result == {"input_registers": [4, 5, 6, 7]}

    def test_non_firmware_range_code3_excluded(self):
        scanner = _FakeScanner(
            failed={"input_registers": {4}},
            unsupported_input_ranges={(4, 4): 3},
        )
        assert _collect_expected_optional_addresses(scanner) == {}

    def test_range_above_15_excluded(self):
        scanner = _FakeScanner(
            failed={"input_registers": {20}},
            unsupported_input_ranges={(16, 25): 2},
        )
        assert _collect_expected_optional_addresses(scanner) == {}

    def test_mixed_firmware_and_non_firmware(self):
        scanner = _FakeScanner(
            failed={"input_registers": {4, 100}},
            unsupported_input_ranges={(4, 4): 2, (100, 100): 2},
        )
        result = _collect_expected_optional_addresses(scanner)
        assert result == {"input_registers": [4]}

    def test_only_intersection_with_failed(self):
        scanner = _FakeScanner(
            failed={"input_registers": {4}},
            unsupported_input_ranges={(0, 15): 2},
        )
        result = _collect_expected_optional_addresses(scanner)
        assert result == {"input_registers": [4]}


class TestSummarizeAddressDictExclude:
    """Tests for _summarize_address_dict with exclude parameter."""

    def test_no_exclude(self):
        result = _summarize_address_dict({"input_registers": [4, 5]})
        assert result == "input_registers: 2"

    def test_exclude_subtracts_count(self):
        result = _summarize_address_dict(
            {"input_registers": [4, 5, 100]},
            exclude={"input_registers": [4, 5]},
        )
        assert result == "input_registers: 1"

    def test_exclude_removes_type_when_all_excluded(self):
        result = _summarize_address_dict(
            {"input_registers": [4]},
            exclude={"input_registers": [4]},
        )
        assert result == _N_A

    def test_exclude_does_not_affect_other_types(self):
        result = _summarize_address_dict(
            {"input_registers": [4], "holding_registers": [100, 101]},
            exclude={"input_registers": [4]},
        )
        assert result == "holding_registers: 2"

    def test_exclude_empty_dict(self):
        result = _summarize_address_dict(
            {"input_registers": [4]},
            exclude={},
        )
        assert result == "input_registers: 1"


@pytest.mark.asyncio
async def test_confirm_placeholders_exclude_expected_optional_from_modbus_errors():
    """Expected-optional firmware failures should not appear in modbus_failed_summary."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "failed_addresses": {
            "modbus_exceptions": {"input_registers": [4]},
            "invalid_values": {},
            "expected_optional": {"input_registers": [4]},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert p["modbus_failed_summary"] == _N_A


@pytest.mark.asyncio
async def test_confirm_placeholders_partial_expected_optional():
    """Only expected-optional addresses are excluded; real failures remain."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "failed_addresses": {
            "modbus_exceptions": {
                "input_registers": [4, 100, 200],
                "holding_registers": [500],
            },
            "invalid_values": {},
            "expected_optional": {"input_registers": [4]},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert "input_registers: 2" in p["modbus_failed_summary"]
    assert "holding_registers: 1" in p["modbus_failed_summary"]


@pytest.mark.asyncio
async def test_confirm_without_expected_optional_field():
    """When expected_optional is absent, behavior is unchanged (backwards compatible)."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "failed_addresses": {
            "modbus_exceptions": {"input_registers": [4]},
            "invalid_values": {},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert "input_registers: 1" in p["modbus_failed_summary"]


class TestKnownMissingClassification:
    """Tests for KNOWN_MISSING_CLASSIFICATION constant."""

    def test_all_19_registers_classified(self):
        from custom_components.thessla_green_modbus.const import KNOWN_MISSING_REGISTERS

        all_known = set()
        for names in KNOWN_MISSING_REGISTERS.values():
            all_known.update(names)

        for name in all_known:
            assert name in KNOWN_MISSING_CLASSIFICATION, (
                f"Register {name!r} in KNOWN_MISSING_REGISTERS but not in "
                f"KNOWN_MISSING_CLASSIFICATION"
            )

    def test_classification_values_are_valid(self):
        valid_categories = {
            "optional_firmware_metadata",
            "optional_feature",
            "hardware_gated",
            "expansion_or_service",
            "newer_firmware_api",
            "internal_service_uart",
            "hardware_sensor_absent",
        }
        for name, category in KNOWN_MISSING_CLASSIFICATION.items():
            assert category in valid_categories, (
                f"Register {name!r} has unknown classification {category!r}"
            )

    def test_real_device_missing_registers_classified(self):
        """All 19 registers from the real-device validation are classified."""
        real_device_missing = {
            "compilation_days",
            "compilation_seconds",
            "version_patch",
            "water_removal_active",
            "cfg_post_heater_mode",
            "cfgszf_fn_new",
            "cfgszf_fw_new",
            "exp_version",
            "filter_exhaust_date_limit_get",
            "filter_supply_date_limit_get",
            "post_heater_on",
            "uart_0_baud",
            "uart_0_id",
            "uart_0_parity",
            "uart_0_stop",
            "uart_1_baud",
            "uart_1_id",
            "uart_1_parity",
            "uart_1_stop",
        }
        for name in real_device_missing:
            assert name in KNOWN_MISSING_CLASSIFICATION
