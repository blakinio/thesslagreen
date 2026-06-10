"""Focused confirm-step config flow user tests."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT

CONF_NAME = "name"
CONF_SLAVE_ID = "slave_id"
DEFAULT_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_SLAVE_ID: 10,
    CONF_NAME: "My Device",
}

_N_A = "—"


class AbortFlow(Exception):
    """Mock AbortFlow to simulate Home Assistant aborts."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@pytest.mark.parametrize(
    "registers,expected_note",
    [
        ("holding", "auto_detected_note_success"),
        (None, "auto_detected_note_limited"),
    ],
)
@pytest.mark.asyncio
async def test_async_step_confirm_auto_detected_note(registers, expected_note):
    """Test confirm step auto detected note for different register counts."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "My Device",
    }
    flow._device_info = {
        "device_name": "ThesslaGreen AirPack",
        "firmware": "1.0",
        "serial_number": "123",
    }
    available_registers = {registers: [1]} if registers else {}
    flow._scan_result = {
        "available_registers": available_registers,
        "capabilities": {},
    }

    translations = {
        "auto_detected_note_success": "Auto-detection successful!",
        "auto_detected_note_limited": "Limited auto-detection - some registers may be missing.",
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value=translations),
    ):
        result = await flow.async_step_confirm()

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["auto_detected_note"] == translations[expected_note]


@pytest.mark.asyncio
async def test_async_step_confirm_capabilities_only_bool():
    """Ensure detected_capabilities_list includes only boolean fields that are True."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "My Device",
    }
    flow._device_info = {}
    flow._scan_result = {
        "available_registers": {},
        "capabilities": {
            "temperature_sensors": {"t1"},
            "expansion_module": True,
            "temperature_sensors_count": 1,
        },
        "register_count": 1,
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    placeholders = result["description_placeholders"]
    assert "Expansion Module" in placeholders["detected_capabilities_list"]
    assert "Temperature Sensors" not in placeholders["detected_capabilities_list"]
    assert "scan_success_rate" not in placeholders


@pytest.mark.asyncio
async def test_confirm_placeholders_no_scan_success_rate():
    """Confirm placeholders must not include the fake scan_success_rate field."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {"register_count": 10}

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    assert "scan_success_rate" not in result["description_placeholders"]


@pytest.mark.asyncio
async def test_confirm_placeholders_scan_stats_present():
    """Scan stats values are surfaced in the placeholders when provided."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "scan_stats": {
            "total_attempts": 20,
            "successful_reads": 18,
            "scan_duration": 3.456,
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert p["total_attempts"] == "20"
    assert p["successful_reads"] == "18"
    assert p["scan_duration"] == "3.5s"


@pytest.mark.asyncio
async def test_confirm_placeholders_missing_stats_show_dash():
    """When scan_stats is absent the placeholders show the neutral N/A indicator."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {"register_count": 5}

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert p["total_attempts"] == _N_A
    assert p["successful_reads"] == _N_A
    assert p["scan_duration"] == _N_A


@pytest.mark.asyncio
async def test_confirm_placeholders_missing_registers_summary():
    """missing_registers are summarised correctly."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "missing_registers": {
            "holding_registers": {"reg_a": 10, "reg_b": 20},
            "input_registers": {},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    summary = result["description_placeholders"]["missing_registers_summary"]
    assert "holding_registers: 2" in summary
    assert "input_registers" not in summary


@pytest.mark.asyncio
async def test_confirm_placeholders_modbus_exceptions_summary():
    """failed_addresses.modbus_exceptions are summarised correctly."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "failed_addresses": {
            "modbus_exceptions": {"holding_registers": {100, 101, 102}},
            "invalid_values": {},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert "holding_registers: 3" in p["modbus_failed_summary"]
    assert p["invalid_values_summary"] == _N_A


@pytest.mark.asyncio
async def test_confirm_placeholders_invalid_values_summary():
    """failed_addresses.invalid_values are summarised correctly."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "failed_addresses": {
            "modbus_exceptions": {},
            "invalid_values": {"input_registers": [200, 201]},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert p["modbus_failed_summary"] == _N_A
    assert "input_registers: 2" in p["invalid_values_summary"]


@pytest.mark.asyncio
async def test_confirm_placeholders_empty_failed_lists_show_dash():
    """Empty missing/failed dicts display the neutral N/A indicator."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "missing_registers": {},
        "failed_addresses": {"modbus_exceptions": {}, "invalid_values": {}},
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert p["missing_registers_summary"] == _N_A
    assert p["modbus_failed_summary"] == _N_A
    assert p["invalid_values_summary"] == _N_A


@pytest.mark.asyncio
async def test_confirm_placeholders_detected_and_not_detected_capabilities():
    """Both detected and not-detected capability lists are present."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 5,
        "capabilities": {
            "expansion_module": True,
            "gwc_system": False,
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    assert "Expansion Module" in p["detected_capabilities_list"]
    assert "Gwc System" in p["not_detected_capabilities_list"]


@pytest.mark.asyncio
async def test_confirm_placeholders_no_entity_count():
    """The placeholders must not include a final entity count field."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {"register_count": 10}

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    entity_count_keys = [k for k in p if "entity" in k.lower() and "count" in k.lower()]
    assert not entity_count_keys, f"Unexpected entity count key(s): {entity_count_keys}"


@pytest.mark.asyncio
async def test_confirm_placeholders_batch_fallback_all_recovered():
    """Batch read fails but all named registers recovered via fallback → modbus_failed_summary is '—'."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 10,
        "failed_addresses": {
            # Batch covered 40-42 but individual probes recovered all three
            "modbus_exceptions": {},
            "invalid_values": {},
            "batch_failures": {"holding_registers": [40, 41, 42]},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    # No true Modbus errors → no error count in summary; batch_failures absent from named error list
    assert "holding_registers: 3" not in p["modbus_failed_summary"]
    assert "holding_registers: 2" not in p["modbus_failed_summary"]
    assert "holding_registers: 1" not in p["modbus_failed_summary"]


@pytest.mark.asyncio
async def test_confirm_placeholders_batch_fallback_one_unrecovered():
    """Batch fails and only one address remains unrecovered → popup shows count 1."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 10,
        "failed_addresses": {
            # Batch covered 40-42; addr 42 could not be recovered by individual probe
            "modbus_exceptions": {"holding_registers": [42]},
            "invalid_values": {},
            "batch_failures": {"holding_registers": [40, 41, 42]},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    # Only the truly unrecovered address counts
    assert "holding_registers: 1" in p["modbus_failed_summary"]
    # The recovered addresses 40, 41 are NOT counted
    assert "holding_registers: 3" not in p["modbus_failed_summary"]


@pytest.mark.asyncio
async def test_confirm_placeholders_expected_optional_still_excluded():
    """expected_optional firmware failures remain excluded from modbus_failed_summary."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 10,
        "failed_addresses": {
            "modbus_exceptions": {"input_registers": [3, 4, 5]},
            "invalid_values": {},
            "expected_optional": {"input_registers": [3, 4, 5]},
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
async def test_confirm_placeholders_deep_scan_batch_failures_not_normal_errors():
    """Deep scan batch failures are shown as diagnostic note, not as normal Modbus error count."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 10,
        "scan_mode": "full",
        "failed_addresses": {
            # Full/deep scan produced 269 raw batch failures, but no named register failures
            "modbus_exceptions": {},
            "invalid_values": {},
            "batch_failures": {
                "input_registers": list(range(22, 291)),  # 269 raw addresses
                "holding_registers": [500],
            },
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    p = result["description_placeholders"]
    summary = p["modbus_failed_summary"]
    # Must NOT look like a normal Modbus error count
    assert "input_registers: 269" not in summary
    assert "holding_registers: 1" not in summary or "deep scan" in summary
    # Must be clearly labelled as deep scan diagnostic, not a plain error count
    assert "deep scan" in summary
    assert "unsupported raw ranges" in summary


@pytest.mark.asyncio
async def test_confirm_placeholders_batch_failures_in_scan_result():
    """batch_failures key is present in scan result failed_addresses for diagnostic access."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {
        "register_count": 10,
        "failed_addresses": {
            "modbus_exceptions": {},
            "invalid_values": {},
            "batch_failures": {"input_registers": [10, 11, 12]},
        },
    }

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        await flow.async_step_confirm()

    # batch_failures are in scan_result, accessible for diagnostics
    assert "batch_failures" in flow._scan_result["failed_addresses"]
    assert flow._scan_result["failed_addresses"]["batch_failures"]["input_registers"] == [
        10,
        11,
        12,
    ]


@pytest.mark.asyncio
async def test_confirm_placeholders_keys_stable():
    """All expected placeholder keys are present and no unexpected keys added."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    flow._data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 1}
    flow._device_info = {}
    flow._scan_result = {"register_count": 5}

    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_confirm()

    expected_keys = {
        "host",
        "port",
        "endpoint",
        "transport_label",
        "transport",
        "slave_id",
        "device_name",
        "firmware_version",
        "serial_number",
        "register_count",
        "total_attempts",
        "successful_reads",
        "scan_duration",
        "missing_registers_summary",
        "modbus_failed_summary",
        "invalid_values_summary",
        "detected_capabilities_list",
        "not_detected_capabilities_list",
        "auto_detected_note",
    }
    assert set(result["description_placeholders"].keys()) == expected_keys


@pytest.mark.asyncio
async def test_confirm_step_aborts_on_existing_entry():
    """Ensure confirming a second flow aborts if unique ID already configured."""

    flow = ConfigFlow()
    flow.hass = None

    user_input = dict(DEFAULT_USER_INPUT)

    validation_result = {
        "title": "Device",
        "device_info": {},
        "scan_result": {},
    }

    # First pass through user step to store data
    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    class AbortFlow(Exception):
        def __init__(self, reason: str) -> None:
            self.reason = reason

    entries: set[str] = set()

    async def async_set_unique_id(self, unique_id: str, **_: Any) -> None:
        self._unique_id = unique_id

    def abort_if_unique_id_configured(self) -> None:
        if getattr(self, "_unique_id", None) in entries:
            raise AbortFlow("already_configured")

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id",
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
        ),
    ):
        await flow.async_step_user(user_input)

    # Attempt to confirm after a duplicate has been configured elsewhere
    with (
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
            side_effect=RuntimeError("already_configured"),
        ),
        pytest.raises(RuntimeError),
    ):
        await flow.async_step_confirm({})

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
        patch.object(ConfigFlow, "async_set_unique_id", async_set_unique_id),
        patch.object(
            ConfigFlow,
            "_abort_if_unique_id_configured",
            abort_if_unique_id_configured,
        ),
    ):
        flow1 = ConfigFlow()
        flow1.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
        flow2 = ConfigFlow()
        flow2.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

        await flow1.async_step_user(user_input)
        await flow2.async_step_user(user_input)

        result1 = await flow1.async_step_confirm({})
        assert result1["type"] == "create_entry"
        entries.add(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input['slave_id']}")

        with pytest.raises(AbortFlow) as err:
            await flow2.async_step_confirm({})
        assert err.value.reason == "already_configured"
