"""Split entity mapping discrete tests."""

from custom_components.thessla_green_modbus import mappings as em
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef


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
