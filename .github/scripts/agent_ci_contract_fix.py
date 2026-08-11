from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace(path: str, old: str, new: str, *, count: int | None = 1) -> None:
    text = read(path)
    actual = text.count(old)
    if count is not None and actual != count:
        raise RuntimeError(f"{path}: expected {count} matches, found {actual}: {old!r}")
    if actual == 0:
        raise RuntimeError(f"{path}: pattern not found: {old!r}")
    write(path, text.replace(old, new, actual if count is None else count))


# Lightweight version-compatibility jobs must not load the repository-wide
# PHCC-dependent conftest; these tests intentionally use only pytest built-ins.
ci = ".github/workflows/ci.yaml"
replace(
    ci,
    "          pytest -q \\\n            tests/test_service_target_contract.py \\\n            tests/test_integration_service_lifecycle.py \\\n            tests/test_repairs.py \\\n            tests/test_write_repair_lifecycle.py",
    "          pytest --noconftest -q \\\n            tests/test_service_target_contract.py \\\n            tests/test_integration_service_lifecycle.py \\\n            tests/test_repairs.py \\\n            tests/test_write_repair_lifecycle.py",
    count=2,
)
replace(
    ci,
    "          pytest -q \\\n            tests/test_modbus_transport_tcp.py \\\n            tests/test_modbus_transport_rtu.py \\\n            tests/test_modbus_transport_raw.py",
    "          pytest --noconftest -q \\\n            tests/test_modbus_transport_tcp.py \\\n            tests/test_modbus_transport_rtu.py \\\n            tests/test_modbus_transport_raw.py",
)

# The volatile energy accumulator was intentionally removed. Keep a regression
# test for instantaneous electrical_power and prove legacy timestamp state is ignored.
path = "tests/test_coordinator_update.py"
text = read(path)
pattern = re.compile(
    r"def test_post_process_data_power_calculation\(\):.*?"
    r"(?=# ---------------------------------------------------------------------------\n# Group R)",
    re.S,
)
replacement = '''def test_post_process_data_power_calculation():
    """Only instantaneous electrical power is exposed from DAC values."""
    coord = _make_coordinator()
    data = {"dac_supply": 5.0, "dac_exhaust": 5.0}
    result = coord._post_process_data(data)
    assert result["electrical_power"] == 20.0
    assert "estimated_power" not in result
    assert "total_energy" not in result


def test_post_process_data_legacy_power_timestamp_is_ignored():
    """Legacy accumulator timestamps cannot recreate volatile energy state."""
    coord = _make_coordinator()
    coord.device_client._last_power_timestamp = "legacy-state"
    data = {"dac_supply": 3.0, "dac_exhaust": 3.0}
    result = coord._post_process_data(data)
    assert result["electrical_power"] == 4.3
    assert "estimated_power" not in result
    assert "total_energy" not in result


'''
text, substitutions = pattern.subn(replacement, text, count=1)
if substitutions != 1:
    raise RuntimeError(f"{path}: failed to replace stale power-accumulator tests")
text = text.replace("from datetime import UTC, datetime\n", "")
text = text.replace("from unittest.mock import patch\n", "")
write(path, text)

# User-flow host/domain tests use simple test doubles. Give them the minimal HA
# config-entry manager needed by the real duplicate-match helper.
path = "tests/test_config_flow_user.py"
text = read(path)
text = text.replace(
    'flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))',
    'flow.hass = SimpleNamespace(\n        config=SimpleNamespace(language="en"),\n        config_entries=SimpleNamespace(async_entries=lambda _domain: []),\n    )',
)
marker = "@pytest.mark.asyncio\nasync def test_unique_id_sanitized():"
idx = text.find(marker)
if idx < 0:
    raise RuntimeError(f"{path}: obsolete unique-id test marker not found")
text = text[:idx] + '''@pytest.mark.asyncio
async def test_host_is_not_used_as_unique_id():
    """Mutable host/IP data is duplicate-match data, never persistent identity."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(
        config=SimpleNamespace(language="en"),
        config_entries=SimpleNamespace(async_entries=lambda _domain: []),
    )

    validation_result = {
        "title": "ThesslaGreen fe80::1",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"
        ) as mock_set_unique_id,
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow._async_abort_entries_match"
        ) as mock_match,
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await flow.async_step_user(
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                CONF_HOST: "fe80::1",
                CONF_PORT: 502,
                CONF_SLAVE_ID: 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    mock_set_unique_id.assert_not_called()
    mock_match.assert_called_once_with(
        {
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
            CONF_HOST: "fe80::1",
            CONF_PORT: 502,
            CONF_SLAVE_ID: 10,
        }
    )
'''
write(path, text)

# Options-flow tests also use a deliberately tiny HA test double.
path = "tests/test_config_flow_options.py"
text = read(path)
text = text.replace(
    "flow.hass = SimpleNamespace()",
    "flow.hass = SimpleNamespace(\n        config_entries=SimpleNamespace(async_entries=lambda _domain: [])\n    )",
)
write(path, text)

# Duplicate-without-serial is now detected through connection matching during
# the user step, before confirm.
write(
    "tests/test_config_flow_user_duplicates.py",
    '''"""Duplicate-handling user-flow tests for config flow."""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_TCP,
)
from homeassistant.const import CONF_HOST, CONF_PORT

CONF_NAME = "name"

DEFAULT_USER_INPUT = {
    CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_SLAVE_ID: 10,
    CONF_NAME: "My Device",
}


class AbortFlow(Exception):
    """Mock AbortFlow to simulate Home Assistant aborts."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@pytest.mark.asyncio
async def test_duplicate_connection_entry_aborts_during_user_step():
    """A device without serial identity is deduplicated by connection data."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow._async_abort_entries_match",
            side_effect=AbortFlow("already_configured"),
        ),
        pytest.raises(AbortFlow) as err,
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

    assert err.value.reason == "already_configured"


@pytest.mark.asyncio
async def test_user_step_duplicate_entry_aborts_silently(caplog):
    """Duplicate device during user step aborts without logging an error."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow._async_abort_entries_match",
            side_effect=AbortFlow("already_configured"),
        ),
        caplog.at_level(logging.ERROR),
        pytest.raises(AbortFlow) as err,
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

    assert err.value.reason == "already_configured"
    assert not caplog.records
''',
)

# Confirm no longer performs host-derived identity/deduplication. Serial
# identity is validated during the user step instead.
path = "tests/test_config_flow_confirm.py"
text = read(path)
marker = "@pytest.mark.asyncio\nasync def test_confirm_step_aborts_on_existing_entry():"
idx = text.find(marker)
if idx < 0:
    raise RuntimeError(f"{path}: old confirm duplicate test marker not found")
text = text[:idx] + '''@pytest.mark.asyncio
async def test_user_step_aborts_on_existing_serial_identity():
    """Stable serial identity is deduplicated before the confirm step."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    validation_result = {
        "title": "ThesslaGreen AirPack",
        "device_info": {"serial_number": "AP4-DUPLICATE"},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow._abort_if_unique_id_configured",
            side_effect=AbortFlow("already_configured"),
        ),
        pytest.raises(AbortFlow) as err,
    ):
        await flow.async_step_user(dict(DEFAULT_USER_INPUT))

    assert err.value.reason == "already_configured"
'''
text = text.replace("from typing import Any\n", "")
write(path, text)

# Remove this one-shot patch machinery from the final tree.
for temporary in (
    ROOT / ".github/scripts/agent_ci_contract_fix.py",
    ROOT / ".github/workflows/agent-ci-contract-fix.yml",
):
    if temporary.exists():
        temporary.unlink()
