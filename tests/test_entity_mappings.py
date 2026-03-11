"""Tests for entity_mappings.py helper functions."""
import logging

import pytest

from custom_components.thessla_green_modbus import entity_mappings as em
from custom_components.thessla_green_modbus.entity_mappings import _infer_icon


# ---------------------------------------------------------------------------
# _infer_icon (lines 191-201)
# ---------------------------------------------------------------------------


def test_infer_icon_temperature_unit():
    assert _infer_icon("x", "°C") == "mdi:thermometer"


def test_infer_icon_temperature_in_name():
    assert _infer_icon("room_temperature", None) == "mdi:thermometer"


def test_infer_icon_flow_unit_m3h():
    assert _infer_icon("x", "m³/h") == "mdi:fan"


def test_infer_icon_flow_unit_m3h_ascii():
    assert _infer_icon("x", "m3/h") == "mdi:fan"


def test_infer_icon_flow_in_name():
    assert _infer_icon("supply_flow_rate", None) == "mdi:fan"


def test_infer_icon_fan_in_name():
    assert _infer_icon("fan_speed", None) == "mdi:fan"


def test_infer_icon_percentage_unit():
    assert _infer_icon("x", "%") == "mdi:percent-outline"


def test_infer_icon_percentage_in_name():
    assert _infer_icon("speed_percentage", None) == "mdi:percent-outline"


def test_infer_icon_time_unit_min():
    assert _infer_icon("x", "min") == "mdi:timer"


def test_infer_icon_time_unit_s():
    assert _infer_icon("x", "s") == "mdi:timer"


def test_infer_icon_time_unit_h():
    assert _infer_icon("x", "h") == "mdi:timer"


def test_infer_icon_time_in_name():
    assert _infer_icon("boost_time", None) == "mdi:timer"


def test_infer_icon_voltage():
    assert _infer_icon("x", "V") == "mdi:sine-wave"


def test_infer_icon_fallback():
    assert _infer_icon("unknown_register", None) == "mdi:numeric"


def test_infer_icon_fallback_unknown_unit():
    assert _infer_icon("x", "ppm") == "mdi:numeric"


# ---------------------------------------------------------------------------
# _resolve_entity_id (lines 154, 179-184)
# ---------------------------------------------------------------------------


def test_map_legacy_entity_id_no_dot_returns_unchanged():
    """No '.' in entity_id → returned immediately (line 154)."""
    result = em.map_legacy_entity_id("no_dot_entity")
    assert result == "no_dot_entity"


def test_map_legacy_entity_id_suffix_warning(monkeypatch, caplog):
    """Legacy suffix 'predkosc' triggers warning and redirect (lines 179-184)."""
    monkeypatch.setattr(em, "_alias_warning_logged", False)
    with caplog.at_level(
        logging.WARNING,
        logger="custom_components.thessla_green_modbus.entity_mappings",
    ):
        result = em.map_legacy_entity_id("number.device_predkosc")
    assert "fan" in result
    assert "Legacy entity ID" in caplog.text


# ---------------------------------------------------------------------------
# Phase 6 — _parse_states pure-function tests
# ---------------------------------------------------------------------------

def test_parse_states_valid_entries():
    """Valid 'value - label' parts are added to state map (line 243)."""
    from custom_components.thessla_green_modbus.entity_mappings import _parse_states

    states = _parse_states("0 - off; 1 - on")
    assert states == {"off": 0, "on": 1}


def test_parse_states_skips_empty_parts():
    """Empty parts from consecutive semicolons are skipped (line 237)."""
    from custom_components.thessla_green_modbus.entity_mappings import _parse_states

    states = _parse_states("0 - off;;1 - on")
    assert states == {"off": 0, "on": 1}
