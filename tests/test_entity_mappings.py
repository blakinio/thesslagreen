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


# ---------------------------------------------------------------------------
# Phase 8 — entity_mappings.py internal function coverage
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.registers.loader import RegisterDef


def test_get_register_info_skips_nameless_registers(monkeypatch):
    """Registers with empty name are skipped during cache init (line 211)."""
    nameless = RegisterDef(function=3, address=100, name="", access="ro")
    named = RegisterDef(function=3, address=101, name="test_valid_reg_p8", access="ro", unit="°C")
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [nameless, named])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    info = em._get_register_info("test_valid_reg_p8")
    assert info is not None
    assert info["unit"] == "°C"
    # Empty name was skipped — not in cache
    assert em._get_register_info("") is None


def test_get_register_info_numeric_suffix_fallback(monkeypatch):
    """Name ending with _<digit> falls back to base name (line 225)."""
    base_reg = RegisterDef(function=3, address=1, name="pump_speed_p8", access="rw", unit="%")
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [base_reg])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    base = em._get_register_info("pump_speed_p8")
    assert base is not None
    # "pump_speed_p8_2" is not in cache, but "pump_speed_p8" is → suffix fallback (line 225)
    fallback = em._get_register_info("pump_speed_p8_2")
    assert fallback == base


def test_load_number_mappings_skips_registers_without_info(monkeypatch):
    """Registers absent from info cache are skipped (line 258)."""
    mystery = RegisterDef(function=3, address=999, name="mystery_reg_p8", access="rw")
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [mystery])
    # Pre-populate cache as empty dict → _get_register_info returns None for all names
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", {})

    result = em._load_number_mappings()
    assert "mystery_reg_p8" not in result


def test_load_number_mappings_skips_enumerated_unit_registers(monkeypatch):
    """Registers with enumerated unit string are excluded from numbers (line 281)."""
    enum_reg = RegisterDef(function=3, address=1, name="mode_reg_p8", access="rw",
                           unit="0 - off; 1 - on")
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [enum_reg])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    result = em._load_number_mappings()
    assert "mode_reg_p8" not in result


def test_load_number_mappings_includes_min_max_when_present(monkeypatch):
    """min and max are conditionally added to config when not None (lines 289, 291)."""
    bounded = RegisterDef(function=3, address=2, name="speed_reg_p8", access="rw",
                          unit="%", min=0, max=100)
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [bounded])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    result = em._load_number_mappings()
    assert "speed_reg_p8" in result
    assert result["speed_reg_p8"]["min"] == 0
    assert result["speed_reg_p8"]["max"] == 100


def test_load_discrete_mappings_skips_coils_not_in_translations(monkeypatch):
    """Coil registers without a matching translation key are skipped (line 382)."""
    original_coils = em.coil_registers
    monkeypatch.setattr(em, "coil_registers",
                        lambda: {"unknown_coil_xyz_p8": 0, **original_coils()})

    binary, _, _ = em._load_discrete_mappings()
    assert "unknown_coil_xyz_p8" not in binary


def test_load_discrete_mappings_skips_discrete_inputs_not_in_translations(monkeypatch):
    """Discrete-input registers without a translation key are skipped (line 389)."""
    original_discrete = em.discrete_input_registers
    monkeypatch.setattr(em, "discrete_input_registers",
                        lambda: {"unknown_discrete_xyz_p8": 0, **original_discrete()})

    binary, _, _ = em._load_discrete_mappings()
    assert "unknown_discrete_xyz_p8" not in binary


def test_load_discrete_mappings_skips_holding_regs_without_info(monkeypatch):
    """Holding registers absent from info cache are skipped (line 399)."""
    original_holding = em.holding_registers
    monkeypatch.setattr(em, "holding_registers",
                        lambda: {"unknown_holding_xyz_p8": 0, **original_holding()})
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    binary, switch, select = em._load_discrete_mappings()
    assert "unknown_holding_xyz_p8" not in binary
    assert "unknown_holding_xyz_p8" not in switch
    assert "unknown_holding_xyz_p8" not in select


def test_load_discrete_mappings_bitmask_no_name_skipped(monkeypatch):
    """Bitmask register with empty name is skipped entirely (line 447)."""
    reg = RegisterDef(function=3, address=300, name="", access="ro",
                      extra={"bitmask": True}, bits=[{"name": "flag_a"}])
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers",
                        lambda *a, **kw: list(original_get_all()) + [reg])

    binary, _, _ = em._load_discrete_mappings()
    # The nameless register's bit must not appear
    assert "_flag_a" not in binary


def test_load_discrete_mappings_bitmask_invalid_function_skipped(monkeypatch):
    """Bitmask register with unrecognised function code is skipped (line 452)."""
    reg = RegisterDef(function=99, address=301, name="weird_bitmask_p8", access="ro",
                      extra={"bitmask": True}, bits=[{"name": "flag_b"}])
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers",
                        lambda *a, **kw: list(original_get_all()) + [reg])

    binary, _, _ = em._load_discrete_mappings()
    assert "weird_bitmask_p8_flag_b" not in binary
    assert "weird_bitmask_p8" not in binary


def test_load_discrete_mappings_bitmask_string_bit_definition(monkeypatch):
    """Non-dict bit definition (plain string) is handled via str() path (line 460)."""
    reg = RegisterDef(function=3, address=302, name="stat_bitmask_p8", access="ro",
                      extra={"bitmask": True}, bits=["flag_c", None])
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers",
                        lambda *a, **kw: list(original_get_all()) + [reg])

    binary, _, _ = em._load_discrete_mappings()
    # String bit_def "flag_c" → creates named entry
    assert "stat_bitmask_p8_flag_c" in binary
    # None bit_def → unnamed_bit=True → generic entry (lines 471, 474-483)
    assert "stat_bitmask_p8" in binary
    assert binary["stat_bitmask_p8"].get("bitmask") is True


def test_load_discrete_mappings_bitmask_unnamed_bit_generic_config(monkeypatch):
    """Unnamed bits trigger generic bitmask fallback config (lines 471, 474-483)."""
    reg = RegisterDef(function=4, address=303, name="error_bitmask_p8", access="ro",
                      extra={"bitmask": True}, bits=[{"name": "e_flag"}, None])
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers",
                        lambda *a, **kw: list(original_get_all()) + [reg])

    binary, _, _ = em._load_discrete_mappings()
    # Named bit creates specific entry
    assert "error_bitmask_p8_e_flag" in binary
    # None bit triggers generic bitmask fallback
    assert "error_bitmask_p8" in binary
    assert binary["error_bitmask_p8"].get("bitmask") is True
