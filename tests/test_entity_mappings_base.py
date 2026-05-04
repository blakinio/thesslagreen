"""Split entity mapping base tests."""

from custom_components.thessla_green_modbus import mappings as em
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef


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

async def test_async_setup_entity_mappings_no_hass():
    """Calling async_setup_entity_mappings(hass=None) hits the else branch (line 1238)."""
    await em.async_setup_entity_mappings(hass=None)
    # Mappings should be populated
    assert isinstance(em.ENTITY_MAPPINGS, dict)
