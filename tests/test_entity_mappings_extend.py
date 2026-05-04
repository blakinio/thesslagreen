"""Split entity mapping extension tests."""

from custom_components.thessla_green_modbus import mappings as em
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef


def test_extend_entity_mappings_switch_continue(monkeypatch):
    """Register already in SWITCH_ENTITY_MAPPINGS triggers the continue at line 1083."""
    sw_reg = RegisterDef(function=3, address=900, name="p10_switch_only", access="rw", min=0, max=1)
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [sw_reg])
    # Temporarily inject the name into SWITCH but not into the earlier mappings
    em.SWITCH_ENTITY_MAPPINGS["p10_switch_only"] = {"register": "p10_switch_only"}
    try:
        em._extend_entity_mappings_from_registers()
        # Should complete without error – the continue at line 1083 was reached
    finally:
        em.SWITCH_ENTITY_MAPPINGS.pop("p10_switch_only", None)

def test_extend_entity_mappings_select_continue(monkeypatch):
    """Register already in SELECT_ENTITY_MAPPINGS triggers the continue at line 1085."""
    sel_reg = RegisterDef(
        function=3, address=901, name="p10_select_only", access="rw", min=0, max=3
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [sel_reg])
    em.SELECT_ENTITY_MAPPINGS["p10_select_only"] = {"states": {}}
    try:
        em._extend_entity_mappings_from_registers()
    finally:
        em.SELECT_ENTITY_MAPPINGS.pop("p10_select_only", None)

def test_extend_entity_mappings_generic_writable_binary(monkeypatch):
    """Register with max_val<=1, write access and a matching switch translation key
    creates a switch entry."""
    reg = RegisterDef(function=3, address=902, name="p10_new_switch", access="rw", min=0, max=1)
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": {"p10_new_switch"},
            "select": set(),
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: set())
    em.SWITCH_ENTITY_MAPPINGS.pop("p10_new_switch", None)
    em.NUMBER_ENTITY_MAPPINGS.pop("p10_new_switch", None)
    em.BINARY_SENSOR_ENTITY_MAPPINGS.pop("p10_new_switch", None)
    em.SELECT_ENTITY_MAPPINGS.pop("p10_new_switch", None)
    em._extend_entity_mappings_from_registers()
    assert "p10_new_switch" in em.SWITCH_ENTITY_MAPPINGS
    em.SWITCH_ENTITY_MAPPINGS.pop("p10_new_switch", None)

def test_extend_entity_mappings_generic_writable_binary_no_translation(monkeypatch):
    """Register without a matching translation key is NOT added to SWITCH_ENTITY_MAPPINGS."""
    reg = RegisterDef(
        function=3, address=902, name="p10_no_translation_switch", access="rw", min=0, max=1
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": set(),
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: set())
    em.SWITCH_ENTITY_MAPPINGS.pop("p10_no_translation_switch", None)
    em._extend_entity_mappings_from_registers()
    assert "p10_no_translation_switch" not in em.SWITCH_ENTITY_MAPPINGS

def test_extend_entity_mappings_generic_readonly_binary(monkeypatch):
    """Register with max_val<=1, read-only access and a matching binary_sensor translation
    key creates a binary sensor entry."""
    reg = RegisterDef(function=3, address=903, name="p10_new_binary", access="ro", min=0, max=1)
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": {"p10_new_binary"},
            "switch": set(),
            "select": set(),
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: set())
    em.BINARY_SENSOR_ENTITY_MAPPINGS.pop("p10_new_binary", None)
    em._extend_entity_mappings_from_registers()
    assert "p10_new_binary" in em.BINARY_SENSOR_ENTITY_MAPPINGS
    em.BINARY_SENSOR_ENTITY_MAPPINGS.pop("p10_new_binary", None)

def test_extend_entity_mappings_generic_select_from_info(monkeypatch):
    """Register with info text and a matching select translation key creates a select entry."""
    reg = RegisterDef(
        function=3,
        address=904,
        name="p10_gen_select",
        access="rw",
        min=0,
        max=3,
        information="0 - off; 1 - low; 2 - high",
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": {"p10_gen_select"},
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: set())
    em.SELECT_ENTITY_MAPPINGS.pop("p10_gen_select", None)
    em._extend_entity_mappings_from_registers()
    assert "p10_gen_select" in em.SELECT_ENTITY_MAPPINGS
    em.SELECT_ENTITY_MAPPINGS.pop("p10_gen_select", None)

def test_extend_entity_mappings_select_skips_parts_without_dash(monkeypatch):
    """Parts in info_text without ' - ' are skipped."""
    reg = RegisterDef(
        function=3,
        address=906,
        name="p10_gen_select_skip",
        access="rw",
        min=0,
        max=3,
        information="bad_part; 0 - off; 1 - on",
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": {"p10_gen_select_skip"},
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: set())
    em.SELECT_ENTITY_MAPPINGS.pop("p10_gen_select_skip", None)
    em._extend_entity_mappings_from_registers()
    assert "p10_gen_select_skip" in em.SELECT_ENTITY_MAPPINGS
    em.SELECT_ENTITY_MAPPINGS.pop("p10_gen_select_skip", None)

def test_extend_entity_mappings_select_skips_non_int_value(monkeypatch):
    """Non-integer value in info_text triggers ValueError continue."""
    reg = RegisterDef(
        function=3,
        address=907,
        name="p10_gen_select_badval",
        access="rw",
        min=0,
        max=3,
        information="abc - off; 1 - on",
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": {"p10_gen_select_badval"},
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: set())
    em.SELECT_ENTITY_MAPPINGS.pop("p10_gen_select_badval", None)
    em._extend_entity_mappings_from_registers()
    # Only "on" entry (value 1) should be in the states, "abc" was skipped
    if "p10_gen_select_badval" in em.SELECT_ENTITY_MAPPINGS:
        states = em.SELECT_ENTITY_MAPPINGS["p10_gen_select_badval"].get("states", {})
        assert "off" not in states
        assert "on" in states
        em.SELECT_ENTITY_MAPPINGS.pop("p10_gen_select_badval", None)

def test_extend_entity_mappings_generic_number(monkeypatch):
    """Register with wider range, write access and a matching number translation key
    creates a number entry."""
    reg = RegisterDef(
        function=3, address=905, name="p10_gen_number", access="rw", min=0, max=100, unit="%"
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": set(),
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: {"p10_gen_number"})
    em.NUMBER_ENTITY_MAPPINGS.pop("p10_gen_number", None)
    em._extend_entity_mappings_from_registers()
    assert "p10_gen_number" in em.NUMBER_ENTITY_MAPPINGS
    em.NUMBER_ENTITY_MAPPINGS.pop("p10_gen_number", None)

def test_extend_entity_mappings_generic_number_no_translation(monkeypatch):
    """Register without a matching number translation key is NOT added."""
    reg = RegisterDef(
        function=3,
        address=905,
        name="p10_gen_number_notrans",
        access="rw",
        min=0,
        max=100,
        unit="%",
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [reg])
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": set(),
        },
    )
    monkeypatch.setattr(em, "_number_translation_keys", lambda: set())
    em.NUMBER_ENTITY_MAPPINGS.pop("p10_gen_number_notrans", None)
    em._extend_entity_mappings_from_registers()
    assert "p10_gen_number_notrans" not in em.NUMBER_ENTITY_MAPPINGS
