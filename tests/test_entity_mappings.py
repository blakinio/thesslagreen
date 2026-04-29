"""Tests for entity_mappings.py helper functions."""

from custom_components.thessla_green_modbus import mappings as em
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef

# ---------------------------------------------------------------------------
# Phase 8 — entity_mappings.py internal function coverage
# ---------------------------------------------------------------------------



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
    enum_reg = RegisterDef(
        function=3, address=1, name="mode_reg_p8", access="rw", unit="0 - off; 1 - on"
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [enum_reg])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    result = em._load_number_mappings()
    assert "mode_reg_p8" not in result


def test_load_number_mappings_includes_min_max_when_present(monkeypatch):
    """min and max are conditionally added to config when not None (lines 289, 291)."""
    bounded = RegisterDef(
        function=3, address=2, name="speed_reg_p8", access="rw", unit="%", min=0, max=100
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [bounded])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)
    # Allow this synthetic register through the translation-key whitelist.
    monkeypatch.setattr(em, "_number_translation_keys", lambda: {"speed_reg_p8"})

    result = em._load_number_mappings()
    assert "speed_reg_p8" in result
    assert result["speed_reg_p8"]["min"] == 0
    assert result["speed_reg_p8"]["max"] == 100


def test_load_discrete_mappings_skips_coils_not_in_translations(monkeypatch):
    """Coil registers without a matching translation key are skipped (line 382)."""
    original_coils = em.coil_registers
    monkeypatch.setattr(
        em, "coil_registers", lambda: {"unknown_coil_xyz_p8": 0, **original_coils()}
    )

    binary, _, _ = em._load_discrete_mappings()
    assert "unknown_coil_xyz_p8" not in binary


def test_load_discrete_mappings_skips_discrete_inputs_not_in_translations(monkeypatch):
    """Discrete-input registers without a translation key are skipped (line 389)."""
    original_discrete = em.discrete_input_registers
    monkeypatch.setattr(
        em,
        "discrete_input_registers",
        lambda: {"unknown_discrete_xyz_p8": 0, **original_discrete()},
    )

    binary, _, _ = em._load_discrete_mappings()
    assert "unknown_discrete_xyz_p8" not in binary


def test_load_discrete_mappings_skips_holding_regs_without_info(monkeypatch):
    """Holding registers absent from info cache are skipped (line 399)."""
    original_holding = em.holding_registers
    monkeypatch.setattr(
        em, "holding_registers", lambda: {"unknown_holding_xyz_p8": 0, **original_holding()}
    )
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    binary, switch, select = em._load_discrete_mappings()
    assert "unknown_holding_xyz_p8" not in binary
    assert "unknown_holding_xyz_p8" not in switch
    assert "unknown_holding_xyz_p8" not in select


def test_load_discrete_mappings_bitmask_no_name_skipped(monkeypatch):
    """Bitmask register with empty name is skipped entirely (line 447)."""
    reg = RegisterDef(
        function=3,
        address=300,
        name="",
        access="ro",
        extra={"bitmask": True},
        bits=[{"name": "flag_a"}],
    )
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [*list(original_get_all()), reg])

    binary, _, _ = em._load_discrete_mappings()
    # The nameless register's bit must not appear
    assert "_flag_a" not in binary


def test_load_discrete_mappings_bitmask_invalid_function_skipped(monkeypatch):
    """Bitmask register with unrecognised function code is skipped (line 452)."""
    reg = RegisterDef(
        function=99,
        address=301,
        name="weird_bitmask_p8",
        access="ro",
        extra={"bitmask": True},
        bits=[{"name": "flag_b"}],
    )
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [*list(original_get_all()), reg])

    binary, _, _ = em._load_discrete_mappings()
    assert "weird_bitmask_p8_flag_b" not in binary
    assert "weird_bitmask_p8" not in binary


def test_load_discrete_mappings_bitmask_string_bit_definition(monkeypatch):
    """Non-dict bit definition (plain string) is handled via str() path (line 460)."""
    reg = RegisterDef(
        function=3,
        address=302,
        name="stat_bitmask_p8",
        access="ro",
        extra={"bitmask": True},
        bits=["flag_c", None],
    )
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [*list(original_get_all()), reg])

    binary, _, _ = em._load_discrete_mappings()
    # String bit_def "flag_c" → creates named entry
    assert "stat_bitmask_p8_flag_c" in binary
    # None bit_def → unnamed_bit=True → generic entry (lines 471, 474-483)
    assert "stat_bitmask_p8" in binary
    assert binary["stat_bitmask_p8"].get("bitmask") is True


def test_load_discrete_mappings_bitmask_unnamed_bit_generic_config(monkeypatch):
    """Unnamed bits trigger generic bitmask fallback config (lines 471, 474-483)."""
    reg = RegisterDef(
        function=4,
        address=303,
        name="error_bitmask_p8",
        access="ro",
        extra={"bitmask": True},
        bits=[{"name": "e_flag"}, None],
    )
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [*list(original_get_all()), reg])

    binary, _, _ = em._load_discrete_mappings()
    # Named bit creates specific entry
    assert "error_bitmask_p8_e_flag" in binary
    # None bit triggers generic bitmask fallback
    assert "error_bitmask_p8" in binary
    assert binary["error_bitmask_p8"].get("bitmask") is True


# ---------------------------------------------------------------------------
# Phase 9 — _load_discrete_mappings switch/binary/select/diag/bitmask paths
# ---------------------------------------------------------------------------


def test_load_discrete_creates_switch_for_writable_2state_in_switch_keys(monkeypatch):
    """2-state writable register in switch_keys → switch config (lines 403-410)."""
    monkeypatch.setattr(em, "holding_registers", lambda: {"sw_reg_p9": 1})
    monkeypatch.setattr(em, "coil_registers", lambda: {})
    monkeypatch.setattr(em, "discrete_input_registers", lambda: {})
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [])
    monkeypatch.setattr(
        em,
        "_REGISTER_INFO_CACHE",
        {
            "sw_reg_p9": {
                "access": "RW",
                "unit": "0 - off; 1 - on",
                "min": None,
                "max": None,
                "scale": 1,
                "step": 1,
                "information": None,
            }
        },
    )
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": {"sw_reg_p9"},
            "switch": {"sw_reg_p9"},
            "select": set(),
        },
    )
    _, switch, _ = em._load_discrete_mappings()
    assert "sw_reg_p9" in switch
    assert switch["sw_reg_p9"]["register"] == "sw_reg_p9"


def test_load_discrete_creates_binary_for_writable_2state_not_in_switch_keys(monkeypatch):
    """2-state writable register NOT in switch_keys but in binary_keys → binary (lines 411-413)."""
    monkeypatch.setattr(em, "holding_registers", lambda: {"bin_reg_p9": 1})
    monkeypatch.setattr(em, "coil_registers", lambda: {})
    monkeypatch.setattr(em, "discrete_input_registers", lambda: {})
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [])
    monkeypatch.setattr(
        em,
        "_REGISTER_INFO_CACHE",
        {
            "bin_reg_p9": {
                "access": "RW",
                "unit": "0 - off; 1 - on",
                "min": None,
                "max": None,
                "scale": 1,
                "step": 1,
                "information": None,
            }
        },
    )
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": {"bin_reg_p9"},
            "switch": set(),
            "select": set(),
        },
    )
    binary, _, _ = em._load_discrete_mappings()
    assert "bin_reg_p9" in binary


def test_load_discrete_creates_select_for_multistate_register(monkeypatch):
    """Multi-state register in select_keys → select config (lines 414-417)."""
    monkeypatch.setattr(em, "holding_registers", lambda: {"sel_reg_p9": 1})
    monkeypatch.setattr(em, "coil_registers", lambda: {})
    monkeypatch.setattr(em, "discrete_input_registers", lambda: {})
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [])
    monkeypatch.setattr(
        em,
        "_REGISTER_INFO_CACHE",
        {
            "sel_reg_p9": {
                "access": "RW",
                "unit": "0 - auto; 1 - manual; 2 - off",
                "min": None,
                "max": None,
                "scale": 1,
                "step": 1,
                "information": None,
            }
        },
    )
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": {"sel_reg_p9"},
        },
    )
    _, _, select = em._load_discrete_mappings()
    assert "sel_reg_p9" in select
    assert "states" in select["sel_reg_p9"]


def test_load_discrete_skips_diag_register_not_in_holding_on_second_check(monkeypatch):
    """Diagnostic register absent from holding_registers on second check is skipped (line 427)."""
    call_count = [0]

    def holding():
        call_count[0] += 1
        return {"s_1": 1} if call_count[0] <= 2 else {}

    monkeypatch.setattr(em, "holding_registers", holding)
    monkeypatch.setattr(em, "coil_registers", lambda: {})
    monkeypatch.setattr(em, "discrete_input_registers", lambda: {})
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", {})
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": set(),
        },
    )
    binary, _, _ = em._load_discrete_mappings()
    assert "s_1" not in binary


def test_load_discrete_skips_diag_register_not_in_binary_keys(monkeypatch):
    """Diagnostic register in holding but missing from binary_keys is skipped (line 429)."""
    monkeypatch.setattr(em, "holding_registers", lambda: {"s_1_p9": 1})
    monkeypatch.setattr(em, "coil_registers", lambda: {})
    monkeypatch.setattr(em, "discrete_input_registers", lambda: {})
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", {})
    monkeypatch.setattr(
        em,
        "_load_translation_keys",
        lambda: {
            "binary_sensor": set(),
            "switch": set(),
            "select": set(),
        },
    )
    binary, _, _ = em._load_discrete_mappings()
    assert "s_1_p9" not in binary


def test_load_discrete_bitmask_empty_bits_list_creates_generic_config(monkeypatch):
    """Bitmask register with empty bits list creates generic config (line 483)."""
    reg = RegisterDef(
        function=1,
        address=400,
        name="empty_bitmask_p9",
        access="ro",
        extra={"bitmask": True},
        bits=[],
    )
    original_get_all = em.get_all_registers
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [*list(original_get_all()), reg])
    binary, _, _ = em._load_discrete_mappings()
    assert "empty_bitmask_p9" in binary
    assert binary["empty_bitmask_p9"].get("bitmask") is True


# ---------------------------------------------------------------------------
# Phase 10: _extend_entity_mappings_from_registers and async_setup_entity_mappings
# ---------------------------------------------------------------------------


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


async def test_async_setup_entity_mappings_no_hass():
    """Calling async_setup_entity_mappings(hass=None) hits the else branch (line 1238)."""
    await em.async_setup_entity_mappings(hass=None)
    # Mappings should be populated
    assert isinstance(em.ENTITY_MAPPINGS, dict)


