# mypy: ignore-errors
"""Tests verifying real-device findings from exported HA state data.

Each test is annotated with one of:
  FIXED                 — bug was corrected in this PR
  CONFIRMED_CORRECT     — behavior is intentional and correct
  NEEDS_VENDOR_CONFIRMATION — further vendor data required before changing
  DEFERRED              — tracked but not changed in this PR
"""

from __future__ import annotations

from custom_components.thessla_green_modbus.binary_sensor import (
    BINARY_SENSOR_DEFINITIONS,
    ThesslaGreenBinarySensor,
)
from custom_components.thessla_green_modbus.fan import ThesslaGreenFan
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.sensor import ThesslaGreenActiveErrorsSensor

from tests.helpers_entity_data_correctness import _make_number

# ---------------------------------------------------------------------------
# Finding 1: fan percentage > 100  (FIXED)
# ---------------------------------------------------------------------------


def test_fan_percentage_109_clamped_to_100(mock_coordinator):
    """FIXED: Fan percentage must not exceed 100 per HA FanEntity spec.

    Real device exported: percentage=109, max_percentage=109.
    Raw value is still accessible via extra_state_attributes['supply_percentage'].
    """
    mock_coordinator.data["min_percentage"] = 10
    mock_coordinator.data["max_percentage"] = 109
    mock_coordinator.data["supply_percentage"] = 109

    fan = ThesslaGreenFan(mock_coordinator)

    assert fan.percentage == 100
    assert fan.extra_state_attributes.get("supply_percentage") == 109


def test_fan_percentage_normal_50_unchanged(mock_coordinator):
    """FIXED: Normal values below 100 are unchanged by the clamp."""
    mock_coordinator.data["min_percentage"] = 10
    mock_coordinator.data["max_percentage"] = 150
    mock_coordinator.data["supply_percentage"] = 50

    fan = ThesslaGreenFan(mock_coordinator)

    assert fan.percentage == 50


def test_fan_percentage_exactly_100_unchanged(mock_coordinator):
    """FIXED: Value of exactly 100 passes through the clamp unchanged."""
    mock_coordinator.data["min_percentage"] = 10
    mock_coordinator.data["max_percentage"] = 150
    mock_coordinator.data["supply_percentage"] = 100

    fan = ThesslaGreenFan(mock_coordinator)

    assert fan.percentage == 100


# ---------------------------------------------------------------------------
# Finding 2: number valid_range mismatch  (NEEDS_VENDOR_CONFIRMATION)
# ---------------------------------------------------------------------------


def test_airing_coef_declared_range(mock_coordinator):
    """NEEDS_VENDOR_CONFIRMATION: airing_coef metadata range is 100–150.

    The real device reported state=50.0 which is outside that range.
    The write range is preserved as declared (100–150) until vendor
    documentation confirms whether 0/50 are valid set-points or
    factory-default placeholders.
    """
    entity = _make_number(mock_coordinator, "airing_coef")
    assert entity._attr_native_min_value == 100
    assert entity._attr_native_max_value == 150


def test_airing_coef_native_value_below_min_does_not_crash(mock_coordinator):
    """NEEDS_VENDOR_CONFIRMATION: reading a value outside the declared range
    must not raise; the entity exposes whatever the device reports.
    """
    mock_coordinator.data["airing_coef"] = 50
    entity = _make_number(mock_coordinator, "airing_coef")
    assert entity.native_value == 50.0


def test_airing_switch_coef_native_value_zero_does_not_crash(mock_coordinator):
    """NEEDS_VENDOR_CONFIRMATION: airing_switch_coef state=0 is outside
    declared range 100–150 but must not cause an exception.
    """
    mock_coordinator.data["airing_switch_coef"] = 0
    entity = _make_number(mock_coordinator, "airing_switch_coef")
    assert entity.native_value == 0.0


# ---------------------------------------------------------------------------
# Finding 3: fire_alarm NC logic  (CONFIRMED_CORRECT)
# ---------------------------------------------------------------------------


def test_fire_alarm_raw_true_means_no_alarm(mock_coordinator):
    """CONFIRMED_CORRECT: fire_alarm uses NC (normally-closed) contact.

    raw_value=True → circuit closed → no alarm → is_on=False / severity=normal.
    raw_value=False → circuit open → alarm triggered → is_on=True / severity=warning.
    """
    defn = BINARY_SENSOR_DEFINITIONS["fire_alarm"]
    reg_type = defn["register_type"]
    address = mock_coordinator._register_maps[reg_type]["fire_alarm"]
    sensor = ThesslaGreenBinarySensor(mock_coordinator, "fire_alarm", address, defn)

    # NC closed → safe
    mock_coordinator.data["fire_alarm"] = True
    assert sensor.is_on is False
    assert sensor.extra_state_attributes.get("severity") == "normal"

    # NC open → alarm
    mock_coordinator.data["fire_alarm"] = False
    assert sensor.is_on is True
    assert sensor.extra_state_attributes.get("severity") == "warning"


def test_fire_alarm_inverted_flag_present():
    """CONFIRMED_CORRECT: The mapping for fire_alarm declares inverted=True."""
    assert BINARY_SENSOR_DEFINITIONS["fire_alarm"].get("inverted") is True


# ---------------------------------------------------------------------------
# Finding 4: dp_duct_filter_overflow  (CONFIRMED_CORRECT)
# ---------------------------------------------------------------------------


def test_dp_duct_filter_overflow_raw_true_is_problem(mock_coordinator):
    """CONFIRMED_CORRECT: dp_duct_filter_overflow raw_value=True → state on (problem).

    This is a real-device problem state — filter pressure differential overflow
    was detected.  No inversion is expected or required.
    """
    defn = BINARY_SENSOR_DEFINITIONS["dp_duct_filter_overflow"]
    reg_type = defn["register_type"]
    address = mock_coordinator._register_maps[reg_type]["dp_duct_filter_overflow"]
    sensor = ThesslaGreenBinarySensor(mock_coordinator, "dp_duct_filter_overflow", address, defn)

    mock_coordinator.data["dp_duct_filter_overflow"] = True
    assert sensor.is_on is True

    mock_coordinator.data["dp_duct_filter_overflow"] = False
    assert sensor.is_on is False


def test_dp_duct_filter_overflow_has_problem_device_class():
    """CONFIRMED_CORRECT: device_class=problem is set correctly."""
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass

    assert (
        BINARY_SENSOR_DEFINITIONS["dp_duct_filter_overflow"]["device_class"]
        == BinarySensorDeviceClass.PROBLEM
    )


# ---------------------------------------------------------------------------
# Finding 5: serial / device_info  (DEFERRED — see docs/real_device_validation.md)
# ---------------------------------------------------------------------------


def test_serial_number_sensor_unavailable_does_not_crash(mock_coordinator):
    """DEFERRED: serial_number sensor must not raise when device_info has no serial."""
    from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
    from custom_components.thessla_green_modbus.sensor import ThesslaGreenSerialNumberSensor

    defn = ENTITY_MAPPINGS["sensor"].get("serial_number", {"translation_key": "serial_number"})
    sensor = ThesslaGreenSerialNumberSensor(mock_coordinator, "serial_number", 100, defn)

    mock_coordinator.device_info = {}
    assert sensor.native_value is None

    mock_coordinator.device_info = {"serial_number": "Unknown"}
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Finding 6: aggregate error/status sensors  (FIXED)
# ---------------------------------------------------------------------------


def test_active_errors_sensor_returns_none_before_first_update(mock_coordinator):
    """FIXED: Before the coordinator has a successful update, sensor returns None.

    native_value=None → HA state «unknown» is correct pre-update.
    """
    mock_coordinator.data = {}
    mock_coordinator.last_update_success = False
    sensor = ThesslaGreenActiveErrorsSensor(mock_coordinator)
    assert sensor.native_value is None


def test_active_errors_sensor_returns_none_string_when_no_errors(mock_coordinator):
    """FIXED: After a successful update with no active errors, sensor returns 'none'.

    This prevents the misleading «unknown» state when the coordinator is
    healthy but no error codes are active.
    """
    mock_coordinator.data = {"e_100": False, "s_200": False}
    mock_coordinator.last_update_success = True
    sensor = ThesslaGreenActiveErrorsSensor(mock_coordinator)
    assert sensor.native_value == "none"


def test_active_errors_sensor_returns_code_when_active(mock_coordinator):
    """FIXED: When an error register is active, native_value lists its code."""
    mock_coordinator.data = {"e_100": True, "s_200": False}
    mock_coordinator.last_update_success = True
    sensor = ThesslaGreenActiveErrorsSensor(mock_coordinator)
    value = sensor.native_value
    assert value is not None
    assert "E100" in value


def test_active_errors_sensor_none_when_all_false_before_update(mock_coordinator):
    """FIXED: All-false error registers before update → None (unknown is correct)."""
    mock_coordinator.data = {"e_100": False, "s_200": False}
    mock_coordinator.last_update_success = False
    sensor = ThesslaGreenActiveErrorsSensor(mock_coordinator)
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Finding 7: _off switch naming  (FIXED — translation only)
# ---------------------------------------------------------------------------


def test_bypass_off_translation_key():
    """FIXED: bypass_off switch uses its own translation_key."""
    mapping = ENTITY_MAPPINGS["switch"]["bypass_off"]
    assert mapping["translation_key"] == "bypass_off"


def test_gwc_off_translation_key():
    """FIXED: gwc_off switch uses its own translation_key."""
    mapping = ENTITY_MAPPINGS["switch"]["gwc_off"]
    assert mapping["translation_key"] == "gwc_off"


# ---------------------------------------------------------------------------
# Finding 8: Polish state wording  (CONFIRMED_CORRECT)
# ---------------------------------------------------------------------------


def test_nie_dziala_only_in_error_code_names():
    """CONFIRMED_CORRECT: 'nie działa' appears only in S30/S31 error-code sensor
    names (supply/exhaust fan not working), which is factually correct for
    those fault codes.  Normal inactive states do not use this phrasing.
    """
    import json

    with open("custom_components/thessla_green_modbus/translations/pl.json") as f:
        pl = json.load(f)

    # Collect every leaf string in the translations
    def _leaves(obj, path=""):
        if isinstance(obj, str):
            yield path, obj
        elif isinstance(obj, dict):
            for k, v in obj.items():
                yield from _leaves(v, f"{path}.{k}")

    problematic = [
        (path, text)
        for path, text in _leaves(pl)
        if "nie dzia" in text.lower() and ".state." in path
    ]
    assert problematic == [], f"Unexpected 'nie działa' in state labels: {problematic}"
