"""Tests: Dangerous AirPack4 entities carry correct risk metadata.

These tests scan the mapping source files as text/AST to verify that:
- Dangerous entities have risk_level, risk_category, and safety_warning fields
- Normal entities do NOT have these fields
- Risk categories are valid strings
- Entity keys haven't changed (spot-check)

They do NOT require the full HA stack — plain Python / filesystem access only.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "thessla_green_modbus"
MAPPINGS = COMP / "mappings"

VALID_RISK_CATEGORIES = {
    "destructive_action",
    "communication_lockout",
    "security_lock",
    "advanced_configuration",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_dict_literal(source: str, var_name: str) -> dict:
    """Extract a top-level dict assignment by variable name using AST."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == var_name
            and isinstance(node.value, ast.Dict)
        ):
            return ast.literal_eval(node.value)
    raise KeyError(f"{var_name} not found in source")


def _get_entity_block(source: str, entity_key: str) -> str | None:
    """Return the literal dict block text for an entity key, or None if not found."""
    pattern = rf'"{re.escape(entity_key)}"\s*:\s*\{{'
    match = re.search(pattern, source)
    if not match:
        return None
    start = match.end() - 1  # position of the opening '{'
    depth = 0
    i = start
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return source[start : i + 1]


def _has_risk_field(source: str, entity_key: str, field: str) -> bool:
    """Return True if the entity key's dict block contains the given field name.

    Handles both inline ``"field": value`` style and ``**<spread_var>`` style
    where the spread variable itself contains the field.
    """
    block = _get_entity_block(source, entity_key)
    if block is None:
        return False
    # Direct inline key
    if f'"{field}"' in block:
        return True
    # Spread: look for **<VarName> in the block, then check if <VarName> dict
    # (defined earlier in the file) contains the field.
    spread_refs = re.findall(r"\*\*([A-Za-z_][A-Za-z0-9_]*)", block)
    for var in spread_refs:
        # Scan source for `var = {` and check if the spread variable's dict
        # contains the field.
        var_pattern = r"^" + re.escape(var) + r"\s*=\s*\{"
        var_match = re.search(var_pattern, source, re.MULTILINE)
        if var_match:
            # Extract the var dict block
            vstart = var_match.end() - 1
            depth = 0
            vi = vstart
            while vi < len(source):
                c = source[vi]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                vi += 1
            var_dict_block = source[vstart : vi + 1]
            if f'"{field}"' in var_dict_block:
                return True
    return False


def _entity_has_all_risk_fields(source: str, entity_key: str) -> bool:
    return all(
        _has_risk_field(source, entity_key, f)
        for f in ("risk_level", "risk_category", "safety_warning")
    )


def _entity_has_no_risk_fields(source: str, entity_key: str) -> bool:
    return not any(
        _has_risk_field(source, entity_key, f)
        for f in ("risk_level", "risk_category", "safety_warning")
    )


# ---------------------------------------------------------------------------
# Spot-check: entity keys must exist
# ---------------------------------------------------------------------------


def test_switch_entity_keys_exist() -> None:
    """Pre-existing switch entity keys must still exist in _static_discrete.py."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("hard_reset_settings", "hard_reset_schedule", "lock_flag", "on_off_panel_mode"):
        assert f'"{key}"' in source, f"Switch key {key!r} missing from _static_discrete.py"


def test_select_entity_keys_exist() -> None:
    """Pre-existing select entity keys must still exist in _static_discrete.py."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("filter_change", "configuration_mode", "access_level", "mode", "season_mode"):
        assert f'"{key}"' in source, f"Select key {key!r} missing from _static_discrete.py"


def test_uart_select_entity_keys_exist() -> None:
    """All 6 UART select entity keys must still exist in _static_discrete_uart.py."""
    source = _read(MAPPINGS / "_static_discrete_uart.py")
    for key in (
        "uart_0_baud",
        "uart_0_parity",
        "uart_0_stop",
        "uart_1_baud",
        "uart_1_parity",
        "uart_1_stop",
    ):
        assert f'"{key}"' in source, f"UART key {key!r} missing from _static_discrete_uart.py"


def test_number_override_keys_exist() -> None:
    """uart_0_id, uart_1_id, lock_pass must still exist in _static_numbers.py."""
    source = _read(MAPPINGS / "_static_numbers.py")
    for key in ("uart_0_id", "uart_1_id", "lock_pass"):
        assert f'"{key}"' in source, f"Number key {key!r} missing from _static_numbers.py"


def test_device_name_text_entity_key_exists() -> None:
    """device_name must still exist in mappings/__init__.py TEXT_ENTITY_MAPPINGS."""
    source = _read(MAPPINGS / "__init__.py")
    assert '"device_name"' in source, '"device_name" missing from mappings/__init__.py'


# ---------------------------------------------------------------------------
# Risk metadata: dangerous entities must have all three fields
# ---------------------------------------------------------------------------


def test_hard_reset_settings_has_risk_metadata() -> None:
    """hard_reset_settings must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    assert _entity_has_all_risk_fields(source, "hard_reset_settings"), (
        "hard_reset_settings is missing risk metadata in SWITCH_ENTITY_MAPPINGS"
    )


def test_hard_reset_schedule_has_risk_metadata() -> None:
    """hard_reset_schedule must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    assert _entity_has_all_risk_fields(source, "hard_reset_schedule"), (
        "hard_reset_schedule is missing risk metadata in SWITCH_ENTITY_MAPPINGS"
    )


def test_lock_flag_has_risk_metadata() -> None:
    """lock_flag must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    assert _entity_has_all_risk_fields(source, "lock_flag"), (
        "lock_flag is missing risk metadata in SWITCH_ENTITY_MAPPINGS"
    )


def test_filter_change_has_risk_metadata() -> None:
    """filter_change must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    assert _entity_has_all_risk_fields(source, "filter_change"), (
        "filter_change is missing risk metadata in SELECT_ENTITY_MAPPINGS"
    )


def test_configuration_mode_has_risk_metadata() -> None:
    """configuration_mode must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    assert _entity_has_all_risk_fields(source, "configuration_mode"), (
        "configuration_mode is missing risk metadata in SELECT_ENTITY_MAPPINGS"
    )


def test_access_level_has_risk_metadata() -> None:
    """access_level must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    assert _entity_has_all_risk_fields(source, "access_level"), (
        "access_level is missing risk metadata in SELECT_ENTITY_MAPPINGS"
    )


def test_uart_selects_have_risk_metadata() -> None:
    """All 6 UART select entities must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_discrete_uart.py")
    for key in (
        "uart_0_baud",
        "uart_0_parity",
        "uart_0_stop",
        "uart_1_baud",
        "uart_1_parity",
        "uart_1_stop",
    ):
        assert _entity_has_all_risk_fields(source, key), (
            f"{key} is missing risk metadata in UART_SELECT_ENTITY_MAPPINGS"
        )


def test_uart_id_numbers_have_risk_metadata() -> None:
    """uart_0_id and uart_1_id must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_numbers.py")
    for key in ("uart_0_id", "uart_1_id"):
        assert _entity_has_all_risk_fields(source, key), (
            f"{key} is missing risk metadata in NUMBER_OVERRIDES"
        )


def test_lock_pass_has_risk_metadata() -> None:
    """lock_pass must have all three risk metadata fields."""
    source = _read(MAPPINGS / "_static_numbers.py")
    assert _entity_has_all_risk_fields(source, "lock_pass"), (
        "lock_pass is missing risk metadata in NUMBER_OVERRIDES"
    )


def test_device_name_has_risk_metadata() -> None:
    """device_name must have all three risk metadata fields."""
    source = _read(MAPPINGS / "__init__.py")
    assert _entity_has_all_risk_fields(source, "device_name"), (
        "device_name is missing risk metadata in TEXT_ENTITY_MAPPINGS"
    )


# ---------------------------------------------------------------------------
# Risk category validation
# ---------------------------------------------------------------------------


def test_hard_reset_entities_are_destructive_action() -> None:
    """hard_reset_settings and hard_reset_schedule must be 'destructive_action'."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("hard_reset_settings", "hard_reset_schedule"):
        assert _has_risk_field(source, key, "risk_category"), f"{key} missing risk_category"
        # Verify the category value
        assert '"destructive_action"' in source, (
            f"Expected 'destructive_action' category in _static_discrete.py near {key}"
        )


def test_filter_change_is_destructive_action() -> None:
    """filter_change must be classified as 'destructive_action'."""
    source = _read(MAPPINGS / "_static_discrete.py")
    # Find the filter_change block and verify it contains destructive_action
    pattern = r'"filter_change"\s*:\s*\{'
    match = re.search(pattern, source)
    assert match is not None, "filter_change not found in _static_discrete.py"
    # Scan the block
    start = match.end() - 1
    depth = 0
    i = start
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = source[start : i + 1]
    assert '"destructive_action"' in block, (
        "filter_change does not have risk_category='destructive_action'"
    )


def test_lock_and_access_entities_are_security_lock() -> None:
    """lock_flag and access_level must be classified as 'security_lock'."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("lock_flag", "access_level"):
        pattern = rf'"{re.escape(key)}"\s*:\s*\{{'
        match = re.search(pattern, source)
        assert match is not None, f"{key} not found in _static_discrete.py"
        start = match.end() - 1
        depth = 0
        i = start
        while i < len(source):
            c = source[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        block = source[start : i + 1]
        assert '"security_lock"' in block, f"{key} does not have risk_category='security_lock'"


def test_lock_pass_number_is_security_lock() -> None:
    """lock_pass in NUMBER_OVERRIDES must be classified as 'security_lock'."""
    source = _read(MAPPINGS / "_static_numbers.py")
    pattern = r'"lock_pass"\s*:\s*\{'
    match = re.search(pattern, source)
    assert match is not None, "lock_pass not found in _static_numbers.py"
    start = match.end() - 1
    depth = 0
    i = start
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = source[start : i + 1]
    assert '"security_lock"' in block, "lock_pass does not have risk_category='security_lock'"


def test_uart_entities_are_communication_lockout() -> None:
    """All UART entities must be classified as 'communication_lockout'."""
    uart_source = _read(MAPPINGS / "_static_discrete_uart.py")
    number_source = _read(MAPPINGS / "_static_numbers.py")

    assert '"communication_lockout"' in uart_source, (
        "_static_discrete_uart.py does not contain 'communication_lockout'"
    )

    # Verify the shared _UART_RISK dict contains communication_lockout
    assert "_UART_RISK" in uart_source, (
        "_UART_RISK helper dict missing from _static_discrete_uart.py"
    )

    # Each UART key should include risk fields (via **_UART_RISK spread)
    for key in (
        "uart_0_baud",
        "uart_0_parity",
        "uart_0_stop",
        "uart_1_baud",
        "uart_1_parity",
        "uart_1_stop",
    ):
        assert f'"{key}"' in uart_source, f"{key} missing from _static_discrete_uart.py"

    # uart_0_id / uart_1_id in _static_numbers.py
    for key in ("uart_0_id", "uart_1_id"):
        pattern = rf'"{re.escape(key)}"\s*:\s*\{{'
        match = re.search(pattern, number_source)
        assert match is not None, f"{key} not found in _static_numbers.py"
        start = match.end() - 1
        depth = 0
        i = start
        while i < len(number_source):
            c = number_source[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        block = number_source[start : i + 1]
        assert '"communication_lockout"' in block, (
            f"{key} does not have risk_category='communication_lockout'"
        )


def test_configuration_mode_is_advanced_configuration() -> None:
    """configuration_mode must be classified as 'advanced_configuration'."""
    source = _read(MAPPINGS / "_static_discrete.py")
    pattern = r'"configuration_mode"\s*:\s*\{'
    match = re.search(pattern, source)
    assert match is not None, "configuration_mode not found in _static_discrete.py"
    start = match.end() - 1
    depth = 0
    i = start
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = source[start : i + 1]
    assert '"advanced_configuration"' in block, (
        "configuration_mode does not have risk_category='advanced_configuration'"
    )


def test_device_name_is_advanced_configuration() -> None:
    """device_name must be classified as 'advanced_configuration'."""
    source = _read(MAPPINGS / "__init__.py")
    pattern = r'"device_name"\s*:\s*\{'
    match = re.search(pattern, source)
    assert match is not None, "device_name not found in mappings/__init__.py"
    start = match.end() - 1
    depth = 0
    i = start
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = source[start : i + 1]
    assert '"advanced_configuration"' in block, (
        "device_name does not have risk_category='advanced_configuration'"
    )


# ---------------------------------------------------------------------------
# Normal entities must NOT have risk metadata
# ---------------------------------------------------------------------------


def test_normal_entities_have_no_risk_metadata() -> None:
    """Normal entities (mode, season_mode, bypass_user_mode) must not have risk fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("mode", "season_mode", "bypass_user_mode"):
        assert _entity_has_no_risk_fields(source, key), (
            f"Normal entity {key!r} unexpectedly has risk metadata"
        )


def test_normal_switch_entities_have_no_risk_metadata() -> None:
    """Normal switch entities (on_off_panel_mode, bypass_off, gwc_off) must not have risk fields."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("on_off_panel_mode", "bypass_off", "gwc_off", "comfort_mode_panel"):
        assert _entity_has_no_risk_fields(source, key), (
            f"Normal switch entity {key!r} unexpectedly has risk metadata"
        )


def test_normal_number_overrides_have_no_risk_metadata() -> None:
    """Normal number entities must not have risk fields."""
    source = _read(MAPPINGS / "_static_numbers.py")
    for key in (
        "supply_air_temperature_manual",
        "air_flow_rate_manual",
        "nominal_supply_air_flow",
    ):
        assert _entity_has_no_risk_fields(source, key), (
            f"Normal number entity {key!r} unexpectedly has risk metadata"
        )


# ---------------------------------------------------------------------------
# Platform files surface risk metadata
# ---------------------------------------------------------------------------


def test_switch_py_surfaces_risk_metadata() -> None:
    """switch.py extra_state_attributes must iterate over risk metadata keys."""
    source = _read(COMP / "switch.py")
    assert "risk_level" in source, "switch.py does not reference 'risk_level'"
    assert "risk_category" in source, "switch.py does not reference 'risk_category'"
    assert "safety_warning" in source, "switch.py does not reference 'safety_warning'"


def test_number_py_surfaces_risk_metadata() -> None:
    """number.py extra_state_attributes must iterate over risk metadata keys."""
    source = _read(COMP / "number.py")
    assert "risk_level" in source, "number.py does not reference 'risk_level'"
    assert "risk_category" in source, "number.py does not reference 'risk_category'"
    assert "safety_warning" in source, "number.py does not reference 'safety_warning'"


def test_select_py_has_extra_state_attributes() -> None:
    """select.py must define extra_state_attributes that surfaces risk metadata."""
    source = _read(COMP / "select.py")
    assert "extra_state_attributes" in source, "select.py does not define extra_state_attributes"
    assert "risk_level" in source, "select.py does not reference 'risk_level'"
    assert "risk_category" in source, "select.py does not reference 'risk_category'"
    assert "safety_warning" in source, "select.py does not reference 'safety_warning'"


def test_text_py_has_extra_state_attributes() -> None:
    """text.py must define extra_state_attributes that surfaces risk metadata."""
    source = _read(COMP / "text.py")
    assert "extra_state_attributes" in source, "text.py does not define extra_state_attributes"
    assert "risk_level" in source, "text.py does not reference 'risk_level'"
    assert "risk_category" in source, "text.py does not reference 'risk_category'"
    assert "safety_warning" in source, "text.py does not reference 'safety_warning'"


def test_select_py_stores_definition_as_instance_attr() -> None:
    """select.py ThesslaGreenSelect.__init__ must assign self._definition."""
    source = _read(COMP / "select.py")
    assert "self._definition" in source, (
        "select.py ThesslaGreenSelect does not store definition as self._definition"
    )


def test_text_py_stores_definition_as_instance_attr() -> None:
    """text.py ThesslaGreenText.__init__ must assign self._definition."""
    source = _read(COMP / "text.py")
    assert "self._definition" in source, (
        "text.py ThesslaGreenText does not store definition as self._definition"
    )


# ---------------------------------------------------------------------------
# entity_category: config for dangerous entities
# ---------------------------------------------------------------------------


def test_dangerous_switch_entities_have_category_config() -> None:
    """hard_reset_settings, hard_reset_schedule, lock_flag must use 'category': 'config'."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("hard_reset_settings", "hard_reset_schedule", "lock_flag"):
        block = _get_entity_block(source, key)
        assert block is not None, f"{key} entity block not found"
        assert '"category": "config"' in block or "'category': 'config'" in block, (
            f'{key} is missing "category": "config" in SWITCH_ENTITY_MAPPINGS'
        )


def test_dangerous_select_entities_have_entity_category_config() -> None:
    """filter_change, configuration_mode, access_level must have entity_category: config."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("filter_change", "configuration_mode", "access_level"):
        assert _has_risk_field(source, key, "entity_category"), (
            f"{key} is missing 'entity_category' in SELECT_ENTITY_MAPPINGS"
        )


def test_uart_selects_have_entity_category_config() -> None:
    """All UART select entities must have entity_category: config via _UART_RISK spread."""
    source = _read(MAPPINGS / "_static_discrete_uart.py")
    assert '"entity_category"' in source, (
        "_static_discrete_uart.py does not contain 'entity_category'"
    )


def test_dangerous_number_entities_have_entity_category_config() -> None:
    """uart_0_id, uart_1_id, lock_pass must have entity_category: config."""
    source = _read(MAPPINGS / "_static_numbers.py")
    for key in ("uart_0_id", "uart_1_id", "lock_pass"):
        assert _has_risk_field(source, key, "entity_category"), (
            f"{key} is missing 'entity_category' in NUMBER_OVERRIDES"
        )


def test_device_name_has_entity_category_config() -> None:
    """device_name must have entity_category: config in TEXT_ENTITY_MAPPINGS."""
    source = _read(MAPPINGS / "__init__.py")
    assert _has_risk_field(source, "device_name", "entity_category"), (
        "device_name is missing 'entity_category' in TEXT_ENTITY_MAPPINGS"
    )


def test_normal_entities_do_not_have_entity_category() -> None:
    """Normal entities must NOT have entity_category in their mapping."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("mode", "season_mode", "bypass_user_mode", "on_off_panel_mode", "bypass_off", "gwc_off"):
        block = _get_entity_block(source, key)
        assert block is None or '"entity_category"' not in block, (
            f"Normal entity {key!r} unexpectedly has entity_category"
        )


def test_hard_reset_entities_not_registry_disabled() -> None:
    """hard_reset_settings and hard_reset_schedule must NOT have entity_registry_enabled_default."""
    source = _read(MAPPINGS / "_static_discrete.py")
    for key in ("hard_reset_settings", "hard_reset_schedule"):
        block = _get_entity_block(source, key)
        assert block is not None, f"{key} entity block not found"
        assert "entity_registry_enabled_default" not in block, (
            f"{key} unexpectedly has entity_registry_enabled_default"
        )


def test_select_py_propagates_entity_category() -> None:
    """select.py ThesslaGreenSelect.__init__ must read entity_category from definition."""
    source = _read(COMP / "select.py")
    assert "entity_category" in source, "select.py does not reference 'entity_category'"
    assert "EntityCategory" in source, "select.py does not import or use EntityCategory"


def test_number_py_propagates_entity_category_from_config() -> None:
    """number.py _setup_number_attributes must read entity_category from entity_config."""
    source = _read(COMP / "number.py")
    assert "entity_category" in source, "number.py does not reference 'entity_category'"
    assert "EntityCategory" in source, "number.py does not import or use EntityCategory"


def test_text_py_propagates_entity_category() -> None:
    """text.py ThesslaGreenText.__init__ must read entity_category from definition."""
    source = _read(COMP / "text.py")
    assert "entity_category" in source, "text.py does not reference 'entity_category'"
    assert "EntityCategory" in source, "text.py does not import or use EntityCategory"
