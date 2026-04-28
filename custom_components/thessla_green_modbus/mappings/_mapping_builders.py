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
    _infer_icon,
    _load_translation_keys,
    _number_translation_keys,
    _parse_states,
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


def _parse_info_states(info_text: str) -> dict[str, int]:
    """Parse '0 - foo; 1 - bar' style info text into state mapping."""
    states: dict[str, int] = {}
    for part in info_text.split(";"):
        part = part.strip()
        if " - " not in part:
            continue
        val_str, label = part.split(" - ", 1)
        try:
            states[_to_snake_case(label)] = int(val_str.strip())
        except ValueError:
            continue
    return states


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

    for reg in _coil_regs():
        if reg not in binary_keys:
            continue
        binary_configs[reg] = {"translation_key": reg, "register_type": "coil_registers"}
    for reg in _discrete_regs():
        if reg not in binary_keys:
            continue
        binary_configs[reg] = {"translation_key": reg, "register_type": "discrete_inputs"}

    for reg in _holding_regs():
        info = _get_info(reg)
        if not info:
            continue
        states = _parse(info.get("unit"))
        if not states:
            continue
        access = (info.get("access") or "").upper()
        cfg: dict[str, Any] = {"translation_key": reg, "register_type": "holding_registers"}
        if len(states) == 2 and set(states.values()) == {0, 1}:
            if "W" in access:
                if reg in switch_keys:
                    cfg["register"] = reg
                    cfg.setdefault("icon", "mdi:toggle-switch")
                    switch_configs[reg] = cfg
                else:
                    if reg in binary_keys:
                        binary_configs[reg] = cfg
        else:
            if reg in select_keys:
                cfg["states"] = states
                select_configs[reg] = cfg

    diag_registers = {"alarm", "error"}
    diag_registers.update(reg for reg in _holding_regs() if re.match(r"[se](?:_|\d)", reg))
    for reg in diag_registers:
        if reg not in _holding_regs() and reg not in {"alarm", "error"}:
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

    func_map = {
        1: "coil_registers",
        2: "discrete_inputs",
        3: "holding_registers",
        4: "input_registers",
    }
    for reg in _get_all():
        if not reg.name:
            continue
        if not reg.extra or not reg.extra.get("bitmask"):
            continue
        register_type = func_map.get(reg.function)
        if not register_type:
            continue
        bits = reg.bits or []
        if bits:
            unnamed_bit = False
            for idx, bit_def in enumerate(bits):
                bit_name = (
                    bit_def.get("name")
                    if isinstance(bit_def, dict)
                    else (str(bit_def) if bit_def is not None else None)
                )
                if bit_name:
                    key = f"{reg.name}_{_to_snake_case(bit_name)}"
                    binary_configs[key] = {
                        "translation_key": key,
                        "register_type": register_type,
                        "register": reg.name,
                        "bit": 1 << idx,
                    }
                else:
                    unnamed_bit = True
            if unnamed_bit:
                binary_configs.setdefault(
                    reg.name,
                    {"translation_key": reg.name, "register_type": register_type, "bitmask": True},
                )
        else:
            binary_configs.setdefault(
                reg.name,
                {"translation_key": reg.name, "register_type": register_type, "bitmask": True},
            )

    return binary_configs, switch_configs, select_configs


def _extend_entity_mappings_from_registers() -> None:
    """Populate entity mappings for registers not explicitly defined.

    Only registers that have a corresponding translation entry are added to
    avoid creating unnamed "Rekuperator" fallback entities for reserved or
    undocumented registers.
    """
    from ..schedule_helpers import PERCENT_10_SELECT_STATES

    _get_all = _resolve("get_all_registers", get_all_registers)
    _tkeys = _resolve("_load_translation_keys", _load_translation_keys)
    _num_tkeys = _resolve("_number_translation_keys", _number_translation_keys)

    parent = _get_parent()

    def _maps(name: str) -> dict[str, Any]:
        return getattr(parent, name, {}) if parent else {}

    number_mappings = _maps("NUMBER_ENTITY_MAPPINGS")
    sensor_mappings = _maps("SENSOR_ENTITY_MAPPINGS")
    binary_mappings = _maps("BINARY_SENSOR_ENTITY_MAPPINGS")
    switch_mappings = _maps("SWITCH_ENTITY_MAPPINGS")
    select_mappings = _maps("SELECT_ENTITY_MAPPINGS")
    text_mappings = _maps("TEXT_ENTITY_MAPPINGS")
    time_mappings = _maps("TIME_ENTITY_MAPPINGS")

    translations = _tkeys()
    binary_keys = translations["binary_sensor"]
    switch_keys = translations["switch"]
    select_keys = translations["select"]
    number_keys = _num_tkeys()

    for reg in _get_all():
        if reg.function != 3 or not reg.name:
            continue
        register = reg.name
        if any(
            _is_already_mapped(register, current_map)
            for current_map in (
                number_mappings,
                sensor_mappings,
                binary_mappings,
                switch_mappings,
                select_mappings,
                text_mappings,
                time_mappings,
            )
        ):
            continue
        if _is_mapped_as_binary_source(register, binary_mappings):
            continue

        if _is_problem_register(register):
            if register not in binary_keys:
                continue
            binary_mappings.setdefault(
                register,
                {
                    "translation_key": register,
                    "icon": "mdi:alert-circle",
                    "register_type": "holding_registers",
                    "device_class": BinarySensorDeviceClass.PROBLEM,
                },
            )
            continue

        if register.startswith("date_time"):
            continue

        if any(register.startswith(prefix) for prefix in BCD_TIME_PREFIXES):
            reg_access = (reg.access or "").upper()
            if register.startswith(_TIME_ENTITY_PREFIXES) and "W" in reg_access:
                time_mappings.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:clock-outline",
                        "register_type": "holding_registers",
                    },
                )
            else:
                sensor_mappings.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:clock-outline",
                        "register_type": "holding_registers",
                    },
                )
            continue

        if register.startswith(("setting_summer_", "setting_winter_")):
            reg_access = (reg.access or "").upper()
            if "W" in reg_access:
                select_mappings.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:fan",
                        "register_type": "holding_registers",
                        "states": PERCENT_10_SELECT_STATES,
                    },
                )
            else:
                sensor_mappings.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:fan",
                        "register_type": "holding_registers",
                    },
                )
            continue

        access = (reg.access or "").upper()
        min_val = reg.min
        max_val = reg.max
        unit = reg.unit
        info_text = reg.information or ""
        scale = reg.multiplier or 1
        step = reg.resolution or scale

        if reg.enum and not (reg.extra and reg.extra.get("bitmask")):
            enum_states = {_to_snake_case(str(v)): int(k) for k, v in reg.enum.items()}
            if len(reg.enum) == 2 and set(int(k) for k in reg.enum) == {0, 1}:
                if "W" in access:
                    if register not in switch_keys:
                        continue
                    switch_mappings.setdefault(
                        register,
                        {
                            "icon": "mdi:toggle-switch",
                            "register": register,
                            "register_type": "holding_registers",
                            "category": None,
                            "translation_key": register,
                        },
                    )
                else:
                    if register not in binary_keys:
                        continue
                    binary_mappings.setdefault(
                        register,
                        {
                            "translation_key": register,
                            "icon": "mdi:checkbox-marked-circle-outline",
                            "register_type": "holding_registers",
                        },
                    )
            elif "W" in access:
                if register not in select_keys:
                    continue
                select_mappings.setdefault(
                    register,
                    {
                        "icon": "mdi:format-list-bulleted",
                        "translation_key": register,
                        "states": enum_states,
                        "register_type": "holding_registers",
                    },
                )
            else:
                sensor_mappings.setdefault(
                    register,
                    {
                        "translation_key": register,
                        "icon": "mdi:information-outline",
                        "register_type": "holding_registers",
                    },
                )
            continue

        if min_val is not None and max_val is not None:
            if max_val <= 1:
                if "W" in access:
                    if register not in switch_keys:
                        continue
                    switch_mappings.setdefault(
                        register,
                        {
                            "icon": "mdi:toggle-switch",
                            "register": register,
                            "register_type": "holding_registers",
                            "category": None,
                            "translation_key": register,
                        },
                    )
                else:
                    if register not in binary_keys:
                        continue
                    binary_mappings.setdefault(
                        register,
                        {
                            "translation_key": register,
                            "icon": "mdi:checkbox-marked-circle-outline",
                            "register_type": "holding_registers",
                        },
                    )
                continue

            if "W" in access and info_text and ";" in info_text and max_val <= 10:
                states = _parse_info_states(info_text)
                if states:
                    if register not in select_keys:
                        continue
                    select_mappings.setdefault(
                        register,
                        {
                            "icon": "mdi:format-list-bulleted",
                            "translation_key": register,
                            "states": states,
                            "register_type": "holding_registers",
                        },
                    )
                    continue

            if "W" in access:
                if register not in number_keys:
                    continue
                number_mappings.setdefault(
                    register,
                    {
                        "unit": unit,
                        "icon": _infer_icon(register, unit),
                        "min": min_val,
                        "max": max_val,
                        "step": step,
                        "scale": scale,
                    },
                )



__all__ = [
    "_TIME_ENTITY_PREFIXES",
    "_extend_entity_mappings_from_registers",
    "_get_parent",
    "_is_already_mapped",
    "_is_mapped_as_binary_source",
    "_is_problem_register",
    "_load_discrete_mappings",
    "_load_number_mappings",
    "_parse_info_states",
    "_resolve",
]
