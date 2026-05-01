"""Discrete mapping loader helpers extracted from mapping builders."""

from __future__ import annotations

from typing import Any

from ._mapping_payloads import classify_discrete_holding_payload


def add_binary_mappings_for_boolean_registers(
    binary_configs: dict[str, dict[str, Any]],
    registers: set[str],
    binary_keys: set[str],
    register_type: str,
) -> None:
    """Populate binary configs with translation/register type for matching registers."""
    for reg in registers:
        if reg not in binary_keys:
            continue
        binary_configs[reg] = {
            "translation_key": reg,
            "register_type": register_type,
        }


def classify_discrete_holding_registers(
    holding_regs: set[str],
    get_info: Any,
    parse_states: Any,
    switch_keys: set[str],
    binary_keys: set[str],
    select_keys: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Classify holding discrete registers into switch/binary/select payload buckets."""
    binary_configs: dict[str, dict[str, Any]] = {}
    switch_configs: dict[str, dict[str, Any]] = {}
    select_configs: dict[str, dict[str, Any]] = {}

    for reg in holding_regs:
        info = get_info(reg)
        if not info:
            continue
        states = parse_states(info.get("unit"))
        if not states:
            continue
        access = (info.get("access") or "").upper()
        target, payload = classify_discrete_holding_payload(
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

    return binary_configs, switch_configs, select_configs


__all__ = [
    "add_binary_mappings_for_boolean_registers",
    "classify_discrete_holding_registers",
]
