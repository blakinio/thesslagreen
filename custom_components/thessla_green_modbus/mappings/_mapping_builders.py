"""Loader functions for entity mapping generation."""

from __future__ import annotations

import re
import sys
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from ..const import (
    coil_registers,
    discrete_input_registers,
    holding_registers,
)
from ..registers.loader import get_all_registers
from ..utils import BCD_TIME_PREFIXES, _to_snake_case
from ._helpers import (
    _get_register_info,
    _load_translation_keys,
    _number_translation_keys,
    _parse_states,
)
from ._mapping_classification import (
    classify_enum_mapping as _classify_enum_mapping,
)
from ._mapping_classification import (
    classify_min_max_mapping as _classify_min_max_mapping,
)
from ._mapping_payloads import (
    classify_discrete_holding_payload as _classify_discrete_holding_payload,
)
from ._mapping_payloads import (
    parse_info_states as _parse_info_states,
)

_TIME_ENTITY_PREFIXES = (
    "schedule_",
    "pres_check_time",
    "airing_summer_",
    "airing_winter_",
    "manual_airing_time_to_start",
    "start_gwc_regen",
    "stop_gwc_regen",
)


def _is_already_mapped(register: str, mappings: dict[str, dict[str, Any]]) -> bool:
    """Return True if *register* already exists in direct mapping keys."""
    return register in mappings


def _is_mapped_as_binary_source(register: str, binary_mappings: dict[str, dict[str, Any]]) -> bool:
    """Return True if a binary mapping references *register* as its source register."""
    return any(v.get("register") == register for v in binary_mappings.values())


def _is_problem_register(register: str) -> bool:
    """Return True for diagnostic/problem registers handled as binary sensors."""
    return register in {"alarm", "error"} or register.startswith(("s_", "e_", "f_"))


def _is_register_mapped_anywhere(register: str, mappings: tuple[dict[str, Any], ...]) -> bool:
    """Return True when *register* exists in any mapping dictionary."""
    return any(_is_already_mapped(register, current_map) for current_map in mappings)


def _build_problem_binary_mapping(register: str) -> dict[str, Any]:
    """Return standard mapping payload for problem-style binary sensors."""
    return {
        "translation_key": register,
        "icon": "mdi:alert-circle",
        "register_type": "holding_registers",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    }


def _build_time_like_mapping(register: str) -> dict[str, Any]:
    """Return standard mapping payload for time-like register entities."""
    return {
        "translation_key": register,
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
    }


def _build_season_setting_mapping(register: str) -> dict[str, Any]:
    """Return standard mapping payload for seasonal settings."""
    from ..schedule_helpers import PERCENT_10_SELECT_STATES

    return {
        "translation_key": register,
        "icon": "mdi:fan",
        "register_type": "holding_registers",
        "states": PERCENT_10_SELECT_STATES,
    }


def _build_base_translation_mapping(register: str, register_type: str) -> dict[str, Any]:
    """Return minimal mapping payload with translation key and register type."""
    return {"translation_key": register, "register_type": register_type}


def _is_binary_state_pair(states: dict[str, int]) -> bool:
    """Return True when parsed states represent a 0/1 pair."""
    return len(states) == 2 and set(states.values()) == {0, 1}


def _diag_register_candidates(holding_regs: set[str]) -> set[str]:
    """Return diagnostic/problem register names to force into binary mappings."""
    diag_registers = {"alarm", "error"}
    diag_registers.update(reg for reg in holding_regs if re.match(r"[se](?:_|\d)", reg))
    return diag_registers



def _apply_diagnostic_binary_overrides(
    diag_registers: set[str],
    holding_regs: set[str],
    binary_keys: set[str],
    binary_configs: dict[str, dict[str, Any]],
    switch_configs: dict[str, dict[str, Any]],
    select_configs: dict[str, dict[str, Any]],
) -> None:
    """Force diagnostic registers into binary mappings and clear conflicting buckets."""
    for reg in diag_registers:
        if reg not in holding_regs and reg not in {"alarm", "error"}:
            continue
        if reg not in binary_keys:
            continue
        binary_configs[reg] = {
            "translation_key": reg,
            "register_type": "holding_registers",
            "entity_category": EntityCategory.DIAGNOSTIC,
        }
        switch_configs.pop(reg, None)
        select_configs.pop(reg, None)

def _iter_bitmask_binary_entries(reg: Any) -> list[tuple[str, dict[str, Any]]]:
    """Build binary mapping entries derived from a bitmask register definition."""
    func_map = {
        1: "coil_registers",
        2: "discrete_inputs",
        3: "holding_registers",
        4: "input_registers",
    }
    register_type = func_map.get(reg.function)
    if not register_type:
        return []

    bits = reg.bits or []
    entries: list[tuple[str, dict[str, Any]]] = []
    unnamed_bit = False
    for idx, bit_def in enumerate(bits):
        bit_name = bit_def.get("name") if isinstance(bit_def, dict) else (str(bit_def) if bit_def is not None else None)
        if bit_name:
            key = f"{reg.name}_{_to_snake_case(bit_name)}"
            entries.append(
                (
                    key,
                    {
                        "translation_key": key,
                        "register_type": register_type,
                        "register": reg.name,
                        "bit": 1 << idx,
                    },
                )
            )
        else:
            unnamed_bit = True

    if not bits or unnamed_bit:
        entries.append(
            (
                reg.name,
                {"translation_key": reg.name, "register_type": register_type, "bitmask": True},
            )
        )
    return entries


def _route_enum_mapping(
    target: str | None,
    register: str,
    payload: dict[str, Any] | None,
    sensor_mappings: dict[str, Any],
    binary_mappings: dict[str, Any],
    switch_mappings: dict[str, Any],
    select_mappings: dict[str, Any],
) -> bool:
    """Apply enum-classification result to mapping stores and return handled state."""
    if target == "switch":
        switch_mappings.setdefault(register, payload)
        return True
    if target == "binary":
        binary_mappings.setdefault(register, payload)
        return True
    if target == "select":
        select_mappings.setdefault(register, payload)
        return True
    if target == "sensor":
        sensor_mappings.setdefault(register, payload)
        return True
    return False


def _route_min_max_mapping(
    target: str | None,
    register: str,
    payload: dict[str, Any] | None,
    number_mappings: dict[str, Any],
    binary_mappings: dict[str, Any],
    switch_mappings: dict[str, Any],
    select_mappings: dict[str, Any],
) -> bool:
    """Apply min/max-classification result to mapping stores and return handled state."""
    if target == "switch":
        switch_mappings.setdefault(register, payload)
        return True
    if target == "binary":
        binary_mappings.setdefault(register, payload)
        return True
    if target == "select":
        select_mappings.setdefault(register, payload)
        return True
    if target == "number":
        number_mappings.setdefault(register, payload)
        return True
    return False


def _is_unmappable_holding_register(
    register: str,
    all_mappings: tuple[dict[str, Any], ...],
    binary_mappings: dict[str, Any],
) -> bool:
    """Return True when register should be skipped before classification."""
    return _is_register_mapped_anywhere(register, all_mappings) or _is_mapped_as_binary_source(register, binary_mappings)


def _route_enum_or_min_max_mapping(
    reg: Any,
    register: str,
    access: str,
    min_val: Any,
    max_val: Any,
    unit: Any,
    info_text: str,
    scale: Any,
    step: Any,
    switch_keys: set[str],
    binary_keys: set[str],
    select_keys: set[str],
    number_keys: set[str],
    sensor_mappings: dict[str, Any],
    number_mappings: dict[str, Any],
    binary_mappings: dict[str, Any],
    switch_mappings: dict[str, Any],
    select_mappings: dict[str, Any],
) -> None:
    """Route register classification to enum or min/max handlers."""
    if reg.enum and not (reg.extra and reg.extra.get("bitmask")):
        target, payload = _classify_enum_mapping(
            register,
            reg.enum,
            access,
            switch_keys,
            binary_keys,
            select_keys,
        )
        _route_enum_mapping(
            target,
            register,
            payload,
            sensor_mappings,
            binary_mappings,
            switch_mappings,
            select_mappings,
        )
        return

    target, payload = _classify_min_max_mapping(
        register,
        access,
        min_val,
        max_val,
        info_text,
        unit,
        step,
        scale,
        switch_keys,
        binary_keys,
        select_keys,
        number_keys,
    )
    _route_min_max_mapping(
        target,
        register,
        payload,
        number_mappings,
        binary_mappings,
        switch_mappings,
        select_mappings,
    )


def _build_sensor_season_setting_mapping(register: str) -> dict[str, Any]:
    """Return read-only season setting mapping payload."""
    return {
        "translation_key": register,
        "icon": "mdi:fan",
        "register_type": "holding_registers",
    }


def _register_context(reg: Any) -> tuple[str, str, Any, Any, Any, str, Any, Any]:
    """Return normalized register fields used by mapping classifiers."""
    return (
        reg.name,
        (reg.access or "").upper(),
        reg.min,
        reg.max,
        reg.unit,
        reg.information or "",
        reg.multiplier or 1,
        reg.resolution or (reg.multiplier or 1),
    )


def _route_problem_mapping(register: str, binary_keys: set[str], binary_mappings: dict[str, Any]) -> bool:
    """Route problem register to binary mappings when translation exists."""
    if register not in binary_keys:
        return False
    binary_mappings.setdefault(register, _build_problem_binary_mapping(register))
    return True


def _route_time_and_season_mappings(
    register: str,
    access: str,
    sensor_mappings: dict[str, Any],
    time_mappings: dict[str, Any],
    select_mappings: dict[str, Any],
) -> bool:
    """Route BCD-time and season-setting registers to dedicated mapping buckets."""
    if any(register.startswith(prefix) for prefix in BCD_TIME_PREFIXES):
        if register.startswith(_TIME_ENTITY_PREFIXES) and "W" in access:
            time_mappings.setdefault(register, _build_time_like_mapping(register))
        else:
            sensor_mappings.setdefault(register, _build_time_like_mapping(register))
        return True

    if register.startswith(("setting_summer_", "setting_winter_")):
        if "W" in access:
            select_mappings.setdefault(register, _build_season_setting_mapping(register))
        else:
            sensor_mappings.setdefault(register, _build_sensor_season_setting_mapping(register))
        return True
    return False


def _resolve_parent_child_mappings(parent: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return mutable mapping dictionaries from parent module."""

    def _maps(name: str) -> dict[str, Any]:
        return getattr(parent, name, {}) if parent else {}

    return (
        _maps("NUMBER_ENTITY_MAPPINGS"),
        _maps("SENSOR_ENTITY_MAPPINGS"),
        _maps("BINARY_SENSOR_ENTITY_MAPPINGS"),
        _maps("SWITCH_ENTITY_MAPPINGS"),
        _maps("SELECT_ENTITY_MAPPINGS"),
        _maps("TEXT_ENTITY_MAPPINGS"),
        _maps("TIME_ENTITY_MAPPINGS"),
    )


def _get_parent() -> Any:
    """Return the parent mappings package module for attribute resolution.

    Design note: all loaders in this module resolve attributes via the parent
    package rather than direct imports. This is intentional — it allows tests
    to patch attributes on the ``mappings`` package and have those patches
    visible to loaders without monkey-patching each individual private function.

    This is NOT a test-induced production smell; it is a deliberate design
    choice for module-level indirection. The pattern is established and
    documented here to prevent accidental removal in future audits.
    """
    return sys.modules.get(__package__)


def _resolve(attr: str, fallback: Any) -> Any:
    """Look up *attr* on the parent mappings module, falling back to *fallback*."""
    parent = _get_parent()
    if parent is not None:
        val = getattr(parent, attr, None)
        if val is not None:
            return val
    return fallback


def _load_number_mappings() -> dict[str, dict[str, Any]]:
    """Build number entity configurations from register metadata."""

    _get_all = _resolve("get_all_registers", get_all_registers)
    _get_info = _resolve("_get_register_info", _get_register_info)
    _parse = _resolve("_parse_states", _parse_states)
    _num_trans = _resolve("_number_translation_keys", _number_translation_keys)

    parent = _get_parent()
    sensor_maps: dict[str, Any] = getattr(parent, "SENSOR_ENTITY_MAPPINGS", {}) if parent else {}
    select_maps: dict[str, Any] = getattr(parent, "SELECT_ENTITY_MAPPINGS", {}) if parent else {}
    switch_maps: dict[str, Any] = getattr(parent, "SWITCH_ENTITY_MAPPINGS", {}) if parent else {}
    num_overrides: dict[str, Any] = getattr(parent, "NUMBER_OVERRIDES", {}) if parent else {}

    number_configs: dict[str, dict[str, Any]] = {}

    for reg in _get_all():
        if reg.function != 3 or not reg.name:
            continue
        if reg.extra and reg.extra.get("type") == "string":
            continue
        register = reg.name
        info = _get_info(register)
        if not info:
            continue

        if register in sensor_maps and "W" not in (info.get("access") or ""):
            continue
        if register in select_maps:
            continue
        if register in switch_maps:
            continue
        if register.startswith("date_time"):
            continue
        if re.match(r"[sef](?:_|\d)", register) or register in {"alarm", "error"}:
            continue
        if any(register.startswith(prefix) for prefix in BCD_TIME_PREFIXES):
            continue
        if register.startswith(("setting_summer_", "setting_winter_")):
            continue
        if _parse(info.get("unit")):
            continue
        if reg.enum and not (reg.extra and reg.extra.get("bitmask")):
            continue
        if register not in _num_trans():
            continue

        cfg: dict[str, Any] = {
            "unit": info.get("unit"),
            "step": info.get("step", 1),
            "scale": info.get("scale", 1),
        }
        if info.get("min") is not None:
            cfg["min"] = info["min"]
        if info.get("max") is not None:
            cfg["max"] = info["max"]

        number_configs[register] = cfg

    for register, override in num_overrides.items():
        number_configs.setdefault(register, {}).update(override)

    return number_configs


def _load_discrete_mappings() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    """Generate mappings for binary_sensor, switch and select entities."""

    _get_all = _resolve("get_all_registers", get_all_registers)
    _get_info = _resolve("_get_register_info", _get_register_info)
    _parse = _resolve("_parse_states", _parse_states)
    _tkeys = _resolve("_load_translation_keys", _load_translation_keys)
    _coil_regs = _resolve("coil_registers", coil_registers)
    _discrete_regs = _resolve("discrete_input_registers", discrete_input_registers)
    _holding_regs = _resolve("holding_registers", holding_registers)

    binary_configs: dict[str, dict[str, Any]] = {}
    switch_configs: dict[str, dict[str, Any]] = {}
    select_configs: dict[str, dict[str, Any]] = {}

    translations = _tkeys()
    binary_keys = translations["binary_sensor"]
    switch_keys = translations["switch"]
    select_keys = translations["select"]

    coil_regs = _coil_regs()
    discrete_regs = _discrete_regs()
    holding_regs = _holding_regs()

    for reg in coil_regs:
        if reg not in binary_keys:
            continue
        binary_configs[reg] = _build_base_translation_mapping(reg, "coil_registers")
    for reg in discrete_regs:
        if reg not in binary_keys:
            continue
        binary_configs[reg] = _build_base_translation_mapping(reg, "discrete_inputs")

    for reg in holding_regs:
        info = _get_info(reg)
        if not info:
            continue
        states = _parse(info.get("unit"))
        if not states:
            continue
        access = (info.get("access") or "").upper()
        target, payload = _classify_discrete_holding_payload(
            register=reg,
            access=access,
            states=states,
            switch_keys=switch_keys,
            binary_keys=binary_keys,
            select_keys=select_keys,
        )
        if target == "switch" and payload:
            switch_configs[reg] = payload
        elif target == "binary" and payload:
            binary_configs[reg] = payload
        elif target == "select" and payload:
            select_configs[reg] = payload

    _apply_diagnostic_binary_overrides(
        _diag_register_candidates(holding_regs),
        holding_regs,
        binary_keys,
        binary_configs,
        switch_configs,
        select_configs,
    )

    for reg in _get_all():
        if not reg.name:
            continue
        if not reg.extra or not reg.extra.get("bitmask"):
            continue
        for key, payload in _iter_bitmask_binary_entries(reg):
            binary_configs.setdefault(key, payload)

    return binary_configs, switch_configs, select_configs


def _extend_entity_mappings_from_registers() -> None:
    """Populate entity mappings for registers not explicitly defined.

    Only registers that have a corresponding translation entry are added to
    avoid creating unnamed "Rekuperator" fallback entities for reserved or
    undocumented registers.
    """
    _get_all = _resolve("get_all_registers", get_all_registers)
    _tkeys = _resolve("_load_translation_keys", _load_translation_keys)
    _num_tkeys = _resolve("_number_translation_keys", _number_translation_keys)

    parent = _get_parent()
    (
        number_mappings,
        sensor_mappings,
        binary_mappings,
        switch_mappings,
        select_mappings,
        text_mappings,
        time_mappings,
    ) = _resolve_parent_child_mappings(parent)

    translations = _tkeys()
    binary_keys = translations["binary_sensor"]
    switch_keys = translations["switch"]
    select_keys = translations["select"]
    number_keys = _num_tkeys()

    for reg in _get_all():
        if reg.function != 3 or not reg.name:
            continue
        register, access, min_val, max_val, unit, info_text, scale, step = _register_context(reg)
        if _is_unmappable_holding_register(
            register,
            all_mappings=(
                number_mappings,
                sensor_mappings,
                binary_mappings,
                switch_mappings,
                select_mappings,
                text_mappings,
                time_mappings,
            ),
            binary_mappings=binary_mappings,
        ):
            continue

        if _is_problem_register(register):
            _route_problem_mapping(register, binary_keys, binary_mappings)
            continue

        if register.startswith("date_time"):
            continue

        if _route_time_and_season_mappings(
            register,
            access,
            sensor_mappings,
            time_mappings,
            select_mappings,
        ):
            continue

        _route_enum_or_min_max_mapping(
            reg=reg,
            register=register,
            access=access,
            min_val=min_val,
            max_val=max_val,
            unit=unit,
            info_text=info_text,
            scale=scale,
            step=step,
            switch_keys=switch_keys,
            binary_keys=binary_keys,
            select_keys=select_keys,
            number_keys=number_keys,
            sensor_mappings=sensor_mappings,
            number_mappings=number_mappings,
            binary_mappings=binary_mappings,
            switch_mappings=switch_mappings,
            select_mappings=select_mappings,
        )



__all__ = [
    "_TIME_ENTITY_PREFIXES",
    "_apply_diagnostic_binary_overrides",
    "_build_base_translation_mapping",
    "_build_problem_binary_mapping",
    "_build_season_setting_mapping",
    "_build_sensor_season_setting_mapping",
    "_build_time_like_mapping",
    "_classify_discrete_holding_payload",
    "_classify_enum_mapping",
    "_classify_min_max_mapping",
    "_diag_register_candidates",
    "_extend_entity_mappings_from_registers",
    "_get_parent",
    "_is_already_mapped",
    "_is_binary_state_pair",
    "_is_mapped_as_binary_source",
    "_is_problem_register",
    "_is_register_mapped_anywhere",
    "_is_unmappable_holding_register",
    "_iter_bitmask_binary_entries",
    "_load_discrete_mappings",
    "_load_number_mappings",
    "_parse_info_states",
    "_register_context",
    "_resolve",
    "_resolve_parent_child_mappings",
    "_route_enum_mapping",
    "_route_enum_or_min_max_mapping",
    "_route_min_max_mapping",
    "_route_problem_mapping",
    "_route_time_and_season_mappings",
]
