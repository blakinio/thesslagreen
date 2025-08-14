"""Ensure translation files don't contain unused keys."""

from custom_components.thessla_green_modbus.const import SPECIAL_FUNCTION_MAP
from tests.test_translations import (
    BINARY_KEYS,
    EN,
    ERROR_KEYS,
    ISSUE_KEYS,
    NUMBER_KEYS,
    PL,
    SELECT_KEYS,
    SENSOR_KEYS,
    SERVICES,
    SWITCH_KEYS as SWITCH_ENTITY_KEYS,
)

SWITCH_KEYS = (
    SWITCH_ENTITY_KEYS
    + ["on_off_panel_mode"]
    + list(SPECIAL_FUNCTION_MAP.keys())
)


def _assert_no_extra_keys(trans, entity_type, valid_keys) -> None:
    section = trans["entity"][entity_type]
    extra = [k for k in section if k not in valid_keys]
    assert not extra, f"Unused {entity_type} translations: {extra}"  # nosec B101


def test_no_unused_translation_keys() -> None:
    for trans in (EN, PL):
        _assert_no_extra_keys(trans, "sensor", SENSOR_KEYS)
        _assert_no_extra_keys(trans, "binary_sensor", BINARY_KEYS)
        _assert_no_extra_keys(trans, "switch", SWITCH_KEYS)
        _assert_no_extra_keys(trans, "select", SELECT_KEYS)
        _assert_no_extra_keys(trans, "number", NUMBER_KEYS)

        extra_errors = [k for k in trans.get("errors", {}) if k not in ERROR_KEYS]
        assert not extra_errors, f"Unused error translations: {extra_errors}"  # nosec B101

        extra_issues = [k for k in trans.get("issues", {}) if k not in ISSUE_KEYS]
        assert not extra_issues, f"Unused issue translations: {extra_issues}"  # nosec B101

        extra_services = [k for k in trans.get("services", {}) if k not in SERVICES]
        assert not extra_services, f"Unused service translations: {extra_services}"  # nosec B101
