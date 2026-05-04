from __future__ import annotations

from typing import Any

from ..utils import BCD_TIME_PREFIXES
from ._mapping_classification import classify_enum_mapping, classify_min_max_mapping
from ._mapping_domain_routes import route_enum_mapping, route_min_max_mapping

TIME_ENTITY_PREFIXES = (
    'schedule_',
    'pres_check_time',
    'airing_summer_',
    'airing_winter_',
    'manual_airing_time_to_start',
    'start_gwc_regen',
    'stop_gwc_regen',
)


def route_time_and_season(register: str, access: str, sensor_mappings: dict[str, Any], time_mappings: dict[str, Any], select_mappings: dict[str, Any]) -> bool:
    if any(register.startswith(prefix) for prefix in BCD_TIME_PREFIXES):
        payload = {'translation_key': register, 'icon': 'mdi:clock-outline', 'register_type': 'holding_registers'}
        if register.startswith(TIME_ENTITY_PREFIXES) and 'W' in access:
            time_mappings.setdefault(register, payload)
        else:
            sensor_mappings.setdefault(register, payload)
        return True
    if register.startswith(('setting_summer_', 'setting_winter_')):
        if 'W' in access:
            select_mappings.setdefault(register, {'translation_key': register, 'icon': 'mdi:fan', 'register_type': 'holding_registers', 'states': __import__('custom_components.thessla_green_modbus.schedule_helpers', fromlist=['PERCENT_10_SELECT_STATES']).PERCENT_10_SELECT_STATES})
        else:
            sensor_mappings.setdefault(register, {'translation_key': register, 'icon': 'mdi:fan', 'register_type': 'holding_registers'})
        return True
    return False


def route_enum_or_min_max(reg: Any, register: str, access: str, min_val: Any, max_val: Any, unit: Any, info_text: str, scale: Any, step: Any, switch_keys: set[str], binary_keys: set[str], select_keys: set[str], number_keys: set[str], sensor_mappings: dict[str, Any], number_mappings: dict[str, Any], binary_mappings: dict[str, Any], switch_mappings: dict[str, Any], select_mappings: dict[str, Any]) -> None:
    if reg.enum and not (reg.extra and reg.extra.get('bitmask')):
        target, payload = classify_enum_mapping(register, reg.enum, access, switch_keys, binary_keys, select_keys)
        route_enum_mapping(target, register, payload, sensor_mappings=sensor_mappings, binary_mappings=binary_mappings, switch_mappings=switch_mappings, select_mappings=select_mappings)
        return
    target, payload = classify_min_max_mapping(register, access, min_val, max_val, info_text, unit, step, scale, switch_keys, binary_keys, select_keys, number_keys)
    route_min_max_mapping(target, register, payload, number_mappings=number_mappings, binary_mappings=binary_mappings, switch_mappings=switch_mappings, select_mappings=select_mappings)
