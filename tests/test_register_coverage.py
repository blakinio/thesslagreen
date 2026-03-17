from __future__ import annotations

import importlib
import json
import re
import sys
import types
from pathlib import Path

from custom_components.thessla_green_modbus.utils import _to_snake_case

INTENTIONAL_OMISSIONS = {
    "exp_version",
    "serial_number_2",
    "serial_number_3",
    "serial_number_4",
    "serial_number_5",
    "serial_number_6",
    # BCD-encoded date/time registers — not exposed as any entity platform
    "date_time",
    "date_time_ddtt",
    "date_time_ggmm",
    "date_time_sscc",
    "date_time_1",
    # String-type holding registers — the scanner reads these specially during
    # device discovery (e.g. device_name is stored in coordinator.device_info).
    # They cannot be represented as a Number entity and have no other mapping.
    "device_name",
    # Reserved / internal registers — device name parts, security keys, and
    # undocumented registers that have no translation key and must not appear
    # as unnamed "Rekuperator" entities in the HA UI.
    "reserved_8145",
    "reserved_8146",
    "reserved_8147",
    "reserved_8148",
    "reserved_8149",
    "reserved_8150",
    "reserved_8151",
    "lock_pass_2",
    # Read-only status / date registers not yet mapped to a platform
    "filter_supply_date_limit_get",
    "filter_exhaust_date_limit_get",
    "post_heater_on",
    # RW configuration registers not yet assigned to a platform
    "cfg_post_heater_mode",
    "cfgszf_fn_new",
    "cfgszf_fw_new",
}

# Minimal Home Assistant stubs required to import entity mappings
ha_const = types.ModuleType("homeassistant.const")
ha_const.PERCENTAGE = "%"
ha_const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
ha_const.UnitOfVolumeFlowRate = types.SimpleNamespace(CUBIC_METERS_PER_HOUR="m³/h")
ha_const.UnitOfElectricPotential = types.SimpleNamespace(VOLT="V")
ha_const.UnitOfTime = types.SimpleNamespace(HOURS="h", DAYS="d", SECONDS="s")
sys.modules.setdefault("homeassistant.const", ha_const)

sensor_mod = types.ModuleType("homeassistant.components.sensor")
sensor_mod.SensorDeviceClass = types.SimpleNamespace(
    TEMPERATURE="temperature",
    VOLTAGE="voltage",
    POWER="power",
    ENERGY="energy",
    EFFICIENCY="efficiency",
)
sensor_mod.SensorStateClass = types.SimpleNamespace(
    MEASUREMENT="measurement", TOTAL_INCREASING="total_increasing"
)
sys.modules.setdefault("homeassistant.components.sensor", sensor_mod)

binary_mod = types.ModuleType("homeassistant.components.binary_sensor")
binary_mod.BinarySensorDeviceClass = types.SimpleNamespace(
    RUNNING="running",
    OPENING="opening",
    POWER="power",
    HEAT="heat",
    CONNECTIVITY="connectivity",
    PROBLEM="problem",
    SAFETY="safety",
    MOISTURE="moisture",
)
sys.modules.setdefault("homeassistant.components.binary_sensor", binary_mod)


def test_all_registers_covered() -> None:
    """Ensure all registers are exposed or intentionally omitted."""

    json_file = (
        Path("custom_components/thessla_green_modbus/registers")
        / "thessla_green_registers_full.json"
    )
    registers = {
        _to_snake_case(r["name"])
        for r in json.loads(json_file.read_text(encoding="utf-8"))["registers"]
        if r.get("name")
    }

    entity_mod = importlib.import_module("custom_components.thessla_green_modbus.entity_mappings")
    exposed: set[str] = set()
    for mapping in entity_mod.ENTITY_MAPPINGS.values():
        exposed.update(mapping.keys())

    diagnostic_regs = {
        n for n in registers if n in {"alarm", "error"} or re.match(r"[es](?:_|\d)", n)
    }

    missing = registers - exposed - diagnostic_regs - INTENTIONAL_OMISSIONS
    assert not missing, f"Unmapped registers: {sorted(missing)}"
