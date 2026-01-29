"""Ensure translation files don't contain unused keys."""

from custom_components.thessla_green_modbus.const import SPECIAL_FUNCTION_MAP
from tests.test_translations import (
    BINARY_KEYS,
    CODE_KEYS,
    EN,
    ISSUE_KEYS,
    NUMBER_KEYS,
    OPTION_ERROR_KEYS,
    OPTION_KEYS,
    PL,
    SELECT_KEYS,
)
from tests.test_translations import SENSOR_KEYS as SENSOR_ENTITY_KEYS
from tests.test_translations import (
    SERVICES,
)
from tests.test_translations import SWITCH_KEYS as SWITCH_ENTITY_KEYS

SENSOR_KEYS = SENSOR_ENTITY_KEYS + ["air_flow_rate_manual", "air_flow_rate_temporary_2"]

SWITCH_KEYS = SWITCH_ENTITY_KEYS + ["on_off_panel_mode"] + list(SPECIAL_FUNCTION_MAP.keys())


def _assert_no_extra_keys(trans, entity_type, valid_keys) -> None:
    section = trans["entity"][entity_type]
    extra = [k for k in section if k not in valid_keys]
    assert not extra, f"Unused {entity_type} translations: {extra}"  # nosec B101


def _assert_no_extra_option_keys(trans) -> None:
    opts = trans["options"]["step"]["init"]
    extra = [k for k in opts["data"] if k not in OPTION_KEYS]
    assert not extra, f"Unused option translations: {extra}"  # nosec B101
    extra_desc = [k for k in opts["data_description"] if k not in OPTION_KEYS]
    assert not extra_desc, f"Unused option descriptions: {extra_desc}"  # nosec B101
    errors = trans["options"].get("error", {})
    extra_err = [k for k in errors if k not in OPTION_ERROR_KEYS]
    assert not extra_err, f"Unused option error translations: {extra_err}"  # nosec B101


def test_no_unused_translation_keys() -> None:
    for trans in (EN, PL):
        _assert_no_extra_keys(trans, "sensor", SENSOR_KEYS)
        _assert_no_extra_keys(trans, "binary_sensor", BINARY_KEYS)
        _assert_no_extra_keys(trans, "switch", SWITCH_KEYS)
        _assert_no_extra_keys(trans, "select", SELECT_KEYS)
        if NUMBER_KEYS:
            _assert_no_extra_keys(trans, "number", NUMBER_KEYS)
        _assert_no_extra_option_keys(trans)

        if CODE_KEYS:
            extra_codes = [k for k in trans.get("codes", {}) if k not in CODE_KEYS]
            assert not extra_codes, f"Unused code translations: {extra_codes}"  # nosec B101

        extra_issues = [k for k in trans.get("issues", {}) if k not in ISSUE_KEYS]
        assert not extra_issues, f"Unused issue translations: {extra_issues}"  # nosec B101

        extra_services = [k for k in trans.get("services", {}) if k not in SERVICES]
        assert not extra_services, f"Unused service translations: {extra_services}"  # nosec B101
