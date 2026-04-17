"""Capability-oriented scanner helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..capability_rules import CAPABILITY_PATTERNS
from ..const import SENSOR_UNAVAILABLE, SENSOR_UNAVAILABLE_REGISTERS
from ..scanner_helpers import REGISTER_ALLOWED_VALUES
from ..utils import BCD_TIME_PREFIXES, decode_bcd_time

if TYPE_CHECKING:
    from ..scanner_device_info import DeviceCapabilities
    from .core import ThesslaGreenDeviceScanner


def is_valid_register_value(scanner: ThesslaGreenDeviceScanner, name: str, value: int) -> bool:
    """Validate a register value against known constraints."""
    if value == 65535:
        return False

    if name in SENSOR_UNAVAILABLE_REGISTERS and value == SENSOR_UNAVAILABLE:
        return True

    if "temperature" in name and value == SENSOR_UNAVAILABLE:
        return True

    allowed = REGISTER_ALLOWED_VALUES.get(name)
    if allowed is not None and value not in allowed:
        return False

    if name.startswith(BCD_TIME_PREFIXES) and name != "schedule_start_time":
        if decode_bcd_time(value) is None:
            return False

    if range_vals := scanner._register_ranges.get(name):
        min_val, max_val = range_vals
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False

    return True


def analyze_capabilities(scanner: ThesslaGreenDeviceScanner) -> DeviceCapabilities:
    """Derive device capabilities from discovered registers."""
    caps = scanner.capabilities.__class__()
    inputs = scanner.available_registers["input_registers"]
    holdings = scanner.available_registers["holding_registers"]
    coils = scanner.available_registers["coil_registers"]
    discretes = scanner.available_registers["discrete_inputs"]

    temp_map = {
        "sensor_outside_temperature": "outside_temperature",
        "sensor_supply_temperature": "supply_temperature",
        "sensor_exhaust_temperature": "exhaust_temperature",
        "sensor_fpx_temperature": "fpx_temperature",
        "sensor_duct_supply_temperature": "duct_supply_temperature",
        "sensor_gwc_temperature": "gwc_temperature",
        "sensor_ambient_temperature": "ambient_temperature",
        "sensor_heating_temperature": "heating_temperature",
    }
    for attr, reg in temp_map.items():
        if reg in inputs:
            setattr(caps, attr, True)
            caps.temperature_sensors.add(reg)

    caps.temperature_sensors_count = len(caps.temperature_sensors)

    if "expansion" in discretes:
        caps.expansion_module = True
    if "gwc" in coils or "gwc_temperature" in inputs:
        caps.gwc_system = True

    if "bypass" in coils:
        caps.bypass_system = True
    if any(reg.startswith("schedule_") for reg in holdings):
        caps.weekly_schedule = True

    if "on_off_panel_mode" in holdings:
        caps.basic_control = True

    if any(
        reg in inputs
        for reg in [
            "constant_flow_active",
            "supply_flow_rate",
            "supply_air_flow",
            "cf_version",
        ]
    ):
        caps.constant_flow = True

    all_registers = inputs | holdings | coils | discretes
    for attr, patterns in CAPABILITY_PATTERNS.items():
        if getattr(caps, attr):
            continue
        if any(pat in reg for reg in all_registers for pat in patterns):
            setattr(caps, attr, True)

    return caps


def filter_unsupported_addresses(
    scanner: ThesslaGreenDeviceScanner, reg_type: str, addrs: set[int]
) -> set[int]:
    """Return failed addresses not covered by unsupported spans."""
    if reg_type == "input_registers":
        ranges = scanner._unsupported_input_ranges
    elif reg_type == "holding_registers":
        ranges = scanner._unsupported_holding_ranges
    else:
        return set(addrs)

    if not ranges:
        return set(addrs)

    return {addr for addr in addrs if not any(start <= addr <= end for start, end in ranges)}


__all__ = ["analyze_capabilities", "filter_unsupported_addresses", "is_valid_register_value"]
