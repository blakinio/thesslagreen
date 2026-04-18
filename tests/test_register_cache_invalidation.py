import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.registers.loader import (
    _REGISTERS_PATH,
    clear_cache,
    load_registers,
    registers_sha256,
)


def test_cache_invalidation_on_content_change(tmp_path: Path) -> None:
    """Changing file contents should invalidate the cache."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text(), encoding="utf-8")

    clear_cache()
    first_hash = registers_sha256(tmp_json)
    first = load_registers(tmp_json)[0]
    assert first.description
    assert first_hash

    data = json.loads(tmp_json.read_text())
    data["registers"][0]["description"] = "changed description"
    tmp_json.write_text(json.dumps(data), encoding="utf-8")

    second_hash = registers_sha256(tmp_json)
    updated = load_registers(tmp_json)[0]
    assert updated.description == "changed description"
    assert first_hash != second_hash

    clear_cache()


def test_cache_invalidation_on_mtime_change(tmp_path: Path) -> None:
    """Touching file without content change should reload registers."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text(), encoding="utf-8")

    clear_cache()
    first_id = id(load_registers(tmp_json))

    os.utime(tmp_json, None)

    second_id = id(load_registers(tmp_json))
    assert first_id != second_id

    clear_cache()


@pytest.fixture
def minimal_coordinator() -> ThesslaGreenModbusCoordinator:
    coord = ThesslaGreenModbusCoordinator.from_legacy(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=5,
        retry=1,
    )
    return coord


def test_apply_scan_cache_keeps_known_missing_for_newer_firmware(
    minimal_coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    """Cache built on FW 4.x must NOT have KNOWN_MISSING_REGISTERS stripped."""
    cache = {
        "available_registers": {
            "input_registers": ["compilation_days", "version_patch", "outside_temperature"],
            "holding_registers": ["uart_0_id", "post_heater_on"],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {"firmware": "4.0.1", "serial_number": "Unknown"},
    }
    assert minimal_coordinator._apply_scan_cache(cache) is True
    assert "compilation_days" in minimal_coordinator.available_registers["input_registers"]
    assert "uart_0_id" in minimal_coordinator.available_registers["holding_registers"]


def test_apply_scan_cache_strips_known_missing_for_fw311(
    minimal_coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    """Cache built on FW 3.11 must have KNOWN_MISSING_REGISTERS stripped."""
    cache = {
        "available_registers": {
            "input_registers": ["compilation_days", "outside_temperature"],
            "holding_registers": ["uart_0_id"],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {"firmware": "3.11", "serial_number": "Unknown"},
    }
    assert minimal_coordinator._apply_scan_cache(cache) is True
    assert "compilation_days" not in minimal_coordinator.available_registers["input_registers"]
    assert "uart_0_id" not in minimal_coordinator.available_registers["holding_registers"]
    assert "outside_temperature" in minimal_coordinator.available_registers["input_registers"]


def test_apply_scan_cache_accepts_set_values(
    minimal_coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    cache = {
        "available_registers": {
            "input_registers": {"outside_temperature"},  # set, not list
            "holding_registers": [],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {"serial_number": "Unknown"},
    }
    assert minimal_coordinator._apply_scan_cache(cache) is True
    assert "outside_temperature" in minimal_coordinator.available_registers["input_registers"]
