"""Legacy mappings and helpers for entity migration."""

from __future__ import annotations

import re

# Map old register keys to current keys for unique_id migration.
#
# DEPRECATION SCHEDULE: entries older than 2 years are candidates for
# removal in 2.7.0+ (planned end-2026). When adding new entries, annotate
# the version in which the rename happened, e.g.:
#   "old_key": "new_key",  # renamed in 2.3.0
LEGACY_KEY_RENAMES: dict[str, str] = {
    # Binary sensor key renames
    "gwc_regeneration_active": "gwc_regen_flag",
    "ahu_filter_overflow": "dp_ahu_filter_overflow",
    "duct_filter_overflow": "dp_duct_filter_overflow",
    "central_heater_overprotection": "post_heater_on",
    "unit_operation_confirmation": "info",
    "water_heater_pump": "duct_water_heater_pump",
    # Sensor key renames
    "maximum_percentage": "max_percentage",
    "minimum_percentage": "min_percentage",
    "time_period": "period",
    "supply_flow_rate_m3_h": "supply_flow_rate",
    "exhaust_flow_rate_m3_h": "exhaust_flow_rate",
    "ahu_stop_alarm_code": "stop_ahu_code",
    "product_key_lock_date_day": "lock_date_00dd",
    "bypass_mode_status": "bypass_mode",
    "comfort_mode_status": "comfort_mode",
    # Switch key renames
    "bypass_active": "bypass_off",
    "gwc_active": "gwc_off",
    "comfort_mode_switch": "comfort_mode_panel",
    "lock": "lock_flag",
    # Select key renames
    "filter_check_day_of_week": "pres_check_day",
    "gwc_regeneration": "gwc_regen",
    "filter_type": "filter_change",
}

# NOT LEGACY — active functional requirement. The e_196_e_199 register is a
# 4-bit bitmask; each bit maps to a separate binary_sensor entity (E196-E199).
# Without this map all 4 bits would collide on the same entity_id.
# Do not remove unless the underlying hardware/protocol changes.
BIT_ENTITY_KEYS: dict[tuple[str, int], str] = {
    # Key format: _to_snake_case(bit_name) inserts underscore before digits,
    # so "e196" → "e_196", giving "e_196_e_199_e_196".
    ("e_196_e_199", 1): "e_196_e_199_e_196",
    ("e_196_e_199", 2): "e_196_e_199_e_197",
    ("e_196_e_199", 4): "e_196_e_199_e_198",
    ("e_196_e_199", 8): "e_196_e_199_e_199",
}


def extract_key_from_unique_id(unique_id: str, prefix: str, slave_id: int | str) -> str | None:
    """Extract register key from entity unique_id.

    Unique ID format: ``{prefix}_{slave_id}_{key}_{addr_part}{bit_suffix}``
    where *addr_part* is a decimal number or the string ``calc``, and
    *bit_suffix* is either empty or ``_bitN``.

    The function first tries an exact prefix match (fast path).  If that
    fails it falls back to scanning for ``_{slave_id}_`` anywhere in the
    unique_id.  This handles cases where the prefix changed between
    registrations (e.g. host-port → serial number after a firmware update)
    so that migration can still rename entities whose prefix no longer
    matches the currently detected one.
    """

    def _parse_rest(rest: str) -> str | None:
        rest = re.sub(r"_bit\d+$", "", rest)
        m = re.match(r"^(.+)_(\d+|calc)$", rest)
        return m.group(1) if m else None

    # Fast path: exact prefix match
    start = f"{prefix}_{slave_id}_"
    if unique_id.startswith(start):
        return _parse_rest(unique_id[len(start) :])

    # Fallback: find _{slave_id}_ anywhere in the unique_id.
    # Handles prefix changes (serial vs host-port) across integration versions.
    slave_marker = f"_{slave_id}_"
    idx = unique_id.find(slave_marker)
    if idx > 0:  # prefix must be non-empty (idx > 0, not >= 0)
        return _parse_rest(unique_id[idx + len(slave_marker) :])

    return None


def extract_legacy_problem_key_from_entity_id(entity_id: str) -> str | None:
    """Extract legacy ``problem``/``problem_N`` key suffix from entity_id."""

    if "." not in entity_id:
        return None
    object_id = entity_id.split(".", 1)[1]
    match = re.search(r"(problem(?:_\d+)?)$", object_id)
    if not match:
        return None
    return match.group(1)
