"""Platform mapping contract tests split from test_entity_mappings.py."""

from custom_components.thessla_green_modbus import mappings as em
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef

# No-duplicate invariants: select/switch registers must not appear in number
# ---------------------------------------------------------------------------


def test_select_registers_not_in_number_mappings():
    """Registers in SELECT_ENTITY_MAPPINGS must not also appear in NUMBER_ENTITY_MAPPINGS.

    Duplication causes HA to create both a Select entity and a Number entity
    for the same register, resulting in duplicate controls visible in the UI.
    """
    duplicates = [
        name for name in em.SELECT_ENTITY_MAPPINGS if name in em.ENTITY_MAPPINGS.get("number", {})
    ]
    assert duplicates == [], (
        f"Registers in both SELECT and NUMBER mappings (would create duplicates): {duplicates}"
    )


def test_switch_registers_not_in_number_mappings():
    """Registers in SWITCH_ENTITY_MAPPINGS must not also appear in NUMBER_ENTITY_MAPPINGS."""
    duplicates = [
        name for name in em.SWITCH_ENTITY_MAPPINGS if name in em.ENTITY_MAPPINGS.get("number", {})
    ]
    assert duplicates == [], (
        f"Registers in both SWITCH and NUMBER mappings (would create duplicates): {duplicates}"
    )


def test_date_time_registers_not_in_number_mappings():
    """BCD date/time registers (date_time_*) must not appear in NUMBER_ENTITY_MAPPINGS.

    These registers store encoded year/month/day values with format-descriptor
    'units' like 'RRMM' and 'DDTT' — not valid measurement units.
    """
    bad = [name for name in em.ENTITY_MAPPINGS.get("number", {}) if name.startswith("date_time")]
    assert bad == [], f"BCD date/time registers found in NUMBER mappings: {bad}"


def test_no_register_in_multiple_platforms():
    """Each register should appear in at most one writable/interactive platform.

    Checks all pairs: number vs select, number vs switch, select vs switch.
    """
    number_keys = set(em.ENTITY_MAPPINGS.get("number", {}))
    select_keys = set(em.SELECT_ENTITY_MAPPINGS)
    switch_keys = set(em.SWITCH_ENTITY_MAPPINGS)

    num_sel = number_keys & select_keys
    num_sw = number_keys & switch_keys
    sel_sw = select_keys & switch_keys

    assert num_sel == set(), f"number ∩ select: {num_sel}"
    assert num_sw == set(), f"number ∩ switch: {num_sw}"
    assert sel_sw == set(), f"select ∩ switch: {sel_sw}"


def test_all_number_entities_have_translation_key():
    """Every Number entity must have a matching translation key in en.json.

    Without a translation key the entity falls back to the device name
    ("Rekuperator"), producing unnamed controls in the HA UI.
    """
    import json
    from pathlib import Path

    en = Path(em.__file__).resolve().parents[1] / "translations" / "en.json"
    number_keys = set(
        json.loads(en.read_text(encoding="utf-8")).get("entity", {}).get("number", {}).keys()
    )
    unnamed = [k for k in em.ENTITY_MAPPINGS.get("number", {}) if k not in number_keys]
    assert unnamed == [], (
        f"Number entities without translation key (would show as 'Rekuperator'): {unnamed}"
    )


def test_rw_schedule_registers_mapped_as_time(monkeypatch):
    """RW schedule_* BCD time registers should end up in TIME_ENTITY_MAPPINGS."""
    sched_reg = RegisterDef(
        function=3, address=16, name="schedule_summer_mon_1", access="RW", min=0, max=2359
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [sched_reg])
    em.SELECT_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
    em.SENSOR_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
    em.TIME_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
    try:
        em._extend_entity_mappings_from_registers()
        assert "schedule_summer_mon_1" in em.TIME_ENTITY_MAPPINGS, (
            "RW schedule register should be a time entity"
        )
        assert "schedule_summer_mon_1" not in em.SENSOR_ENTITY_MAPPINGS, (
            "RW schedule register must not also be a sensor"
        )
        assert "schedule_summer_mon_1" not in em.SELECT_ENTITY_MAPPINGS, (
            "RW schedule register must not also be a select"
        )
        defn = em.TIME_ENTITY_MAPPINGS["schedule_summer_mon_1"]
        assert defn["icon"] == "mdi:clock-outline"
    finally:
        em.SELECT_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
        em.SENSOR_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
        em.TIME_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)


def test_ro_schedule_registers_mapped_as_sensor(monkeypatch):
    """Read-only schedule_* BCD time registers remain sensors."""
    sched_reg = RegisterDef(
        function=3, address=16, name="schedule_summer_mon_1", access="R", min=0, max=2359
    )
    monkeypatch.setattr(em, "get_all_registers", lambda *a, **kw: [sched_reg])
    orig_select = em.SELECT_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
    orig_sensor = em.SENSOR_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
    try:
        em._extend_entity_mappings_from_registers()
        assert "schedule_summer_mon_1" in em.SENSOR_ENTITY_MAPPINGS, (
            "RO schedule register should remain a sensor"
        )
        assert "schedule_summer_mon_1" not in em.SELECT_ENTITY_MAPPINGS
    finally:
        em.SELECT_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
        em.SENSOR_ENTITY_MAPPINGS.pop("schedule_summer_mon_1", None)
        if orig_select is not None:
            em.SELECT_ENTITY_MAPPINGS["schedule_summer_mon_1"] = orig_select
        if orig_sensor is not None:
            em.SENSOR_ENTITY_MAPPINGS["schedule_summer_mon_1"] = orig_sensor
