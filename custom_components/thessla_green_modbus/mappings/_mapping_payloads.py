"""Shared payload and parsing helpers for mapping classification/builders."""

from __future__ import annotations

from typing import Any

from ..utils import _to_snake_case


def build_switch_mapping(register: str) -> dict[str, Any]:
    """Return standard mapping payload for writable on/off style registers."""
    return {
        "icon": "mdi:toggle-switch",
        "register": register,
        "register_type": "holding_registers",
        "category": None,
        "translation_key": register,
    }


def build_binary_toggle_mapping(register: str) -> dict[str, Any]:
    """Return standard mapping payload for read-only on/off style registers."""
    return {
        "translation_key": register,
        "icon": "mdi:checkbox-marked-circle-outline",
        "register_type": "holding_registers",
    }


def build_select_mapping(register: str, states: dict[str, int]) -> dict[str, Any]:
    """Return standard mapping payload for select entities based on states."""
    return {
        "icon": "mdi:format-list-bulleted",
        "translation_key": register,
        "states": states,
        "register_type": "holding_registers",
    }


def parse_info_states(info_text: str) -> dict[str, int]:
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


def classify_discrete_holding_payload(
    register: str,
    access: str,
    states: dict[str, int],
    switch_keys: set[str],
    binary_keys: set[str],
    select_keys: set[str],
) -> tuple[str | None, dict[str, Any] | None]:
    """Classify discrete holding register payload into switch/binary/select buckets."""
    cfg: dict[str, Any] = {
        "translation_key": register,
        "register_type": "holding_registers",
    }

    if len(states) == 2 and set(states.values()) == {0, 1}:
        if "W" in access and register in switch_keys:
            cfg["register"] = register
            cfg.setdefault("icon", "mdi:toggle-switch")
            return "switch", cfg
        if register in binary_keys:
            return "binary", cfg
        return None, None

    if register in select_keys:
        cfg["states"] = states
        return "select", cfg

    return None, None
