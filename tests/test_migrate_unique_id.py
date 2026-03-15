import pytest

from custom_components.thessla_green_modbus.const import (
    DOMAIN,
    device_unique_id_prefix,
    migrate_unique_id,
)

HOST = "fd00:1:2::1"
PORT = 502
SLAVE = 10
REGISTER_NAME = "supply_flow_rate"
REGISTER_ADDRESS = 274


def test_migrate_unique_id_with_serial():
    unique_id = f"{DOMAIN}_{HOST}_{PORT}_{SLAVE}_{REGISTER_NAME}"
    prefix = device_unique_id_prefix("ABC123", HOST, PORT)
    new_uid = migrate_unique_id(
        unique_id,
        serial_number="ABC123",
        host=HOST,
        port=PORT,
        slave_id=SLAVE,
    )
    assert new_uid == f"{prefix}_{SLAVE}_{REGISTER_NAME}_{REGISTER_ADDRESS}"


def test_migrate_unique_id_without_serial():
    unique_id = f"{DOMAIN}_{HOST}_{PORT}_{SLAVE}_{REGISTER_NAME}"
    prefix = device_unique_id_prefix(None, HOST, PORT)
    new_uid = migrate_unique_id(
        unique_id,
        serial_number=None,
        host=HOST,
        port=PORT,
        slave_id=SLAVE,
    )
    assert new_uid == f"{prefix}_{SLAVE}_{REGISTER_NAME}_{REGISTER_ADDRESS}"  # nosec B101  # nosec B101


def test_migrate_unique_id_register_name_to_address():
    unique_id = f"{DOMAIN}_ABC123_{SLAVE}_{REGISTER_NAME}"
    prefix = device_unique_id_prefix("ABC123", HOST, PORT)
    new_uid = migrate_unique_id(
        unique_id,
        serial_number="ABC123",
        host=HOST,
        port=PORT,
        slave_id=SLAVE,
    )
    assert new_uid == f"{prefix}_{SLAVE}_{REGISTER_NAME}_{REGISTER_ADDRESS}"  # nosec B101


# ---------------------------------------------------------------------------
# device_unique_id_prefix fallback paths (lines 229-233)
# ---------------------------------------------------------------------------


def test_device_unique_id_prefix_host_only():
    """host_part returned alone when port is None (lines 229-230)."""
    result = device_unique_id_prefix(None, "192.168.1.1", None)
    assert result == "192-168-1-1"  # nosec B101


def test_device_unique_id_prefix_port_only():
    """Returns 'device-{port}' when host is empty and port given (lines 231-232)."""
    result = device_unique_id_prefix(None, "", 502)
    assert result == "device-502"  # nosec B101


def test_device_unique_id_prefix_neither():
    """Returns 'device' when both host empty and port None (line 233)."""
    result = device_unique_id_prefix(None, "", None)
    assert result == "device"  # nosec B101


# ---------------------------------------------------------------------------
# migrate_unique_id edge cases (lines 267-268, 272, 277, 313-320, 330-341)
# ---------------------------------------------------------------------------


def test_migrate_unique_id_strips_m3h_suffix():
    """_m3h suffix stripped before further processing (lines 267-268)."""
    uid_base = f"{DOMAIN}_{HOST}_{PORT}_{SLAVE}_{REGISTER_NAME}"
    uid_with_m3h = f"{uid_base}_m3h"
    result = migrate_unique_id(
        uid_with_m3h, serial_number=None, host=HOST, port=PORT, slave_id=SLAVE
    )
    expected = migrate_unique_id(
        uid_base, serial_number=None, host=HOST, port=PORT, slave_id=SLAVE
    )
    assert result == expected  # nosec B101


def test_migrate_unique_id_already_new_format():
    """uid already matching new format pattern is returned unchanged (line 272).

    The pattern uses [^_]+ for the entity key, so a key without underscores is
    required.  'mode' is a real holding register key at address 4208.
    """
    prefix = device_unique_id_prefix(None, HOST, PORT)
    # Use entity key "mode" (no underscores) at address 4208
    uid = f"{prefix}_{SLAVE}_mode_4208"
    result = migrate_unique_id(uid, serial_number=None, host=HOST, port=PORT, slave_id=SLAVE)
    assert result == uid  # nosec B101


def test_migrate_unique_id_no_domain_prefix():
    """uid without DOMAIN prefix → uid_no_domain = uid (line 277)."""
    # Build a uid that does NOT start with "thessla_green_modbus_"
    uid = f"custom_prefix-{PORT}-{SLAVE}-{REGISTER_NAME}"
    result = migrate_unique_id(uid, serial_number=None, host=HOST, port=PORT, slave_id=SLAVE)
    assert result is not None  # nosec B101
    assert REGISTER_NAME in result  # nosec B101


def test_migrate_unique_id_address_based_lookup():
    """Numeric remainder triggers reverse_by_address lookup (lines 313-320)."""
    # remainder = str(REGISTER_ADDRESS) = "274" → numeric regex matches → address path
    uid = f"{DOMAIN}_{HOST}_{PORT}_{SLAVE}_{REGISTER_ADDRESS}"
    result = migrate_unique_id(uid, serial_number=None, host=HOST, port=PORT, slave_id=SLAVE)
    assert result is not None  # nosec B101
    assert str(REGISTER_ADDRESS) in result  # nosec B101


def test_migrate_unique_id_register_to_key_lookup(monkeypatch):
    """register_to_key path: remainder is register_name but not entity key (lines 330-333)."""
    from custom_components.thessla_green_modbus import const as const_mod

    # Inject lookup: entity key "flow_entity" uses register "supply_flow_rate"
    # lookup keys are entity keys — "supply_flow_rate" is NOT in lookup as a key
    fake_lookup = {
        "flow_entity": ("supply_flow_rate", "input_registers", None),
    }
    monkeypatch.setattr(const_mod, "_ENTITY_LOOKUP", fake_lookup)

    # remainder = "supply_flow_rate" → not in lookup → elif register_to_key path
    uid = f"{DOMAIN}_{HOST}_{PORT}_{SLAVE}_supply_flow_rate"
    result = migrate_unique_id(uid, serial_number=None, host=HOST, port=PORT, slave_id=SLAVE)

    # "supply_flow_rate" → register_to_key["supply_flow_rate"] = "flow_entity"
    # address 274 → base_uid = "10_flow_entity_274"
    assert "flow_entity" in result  # nosec B101
    assert str(REGISTER_ADDRESS) in result  # nosec B101

    # Restore cache so subsequent tests see real lookup
    monkeypatch.setattr(const_mod, "_ENTITY_LOOKUP", None)


def test_migrate_unique_id_fan_remainder():
    """'fan' remainder produces base_uid with _fan_0 (lines 340-341)."""
    uid = f"{DOMAIN}_{HOST}_{PORT}_{SLAVE}_fan"
    result = migrate_unique_id(uid, serial_number=None, host=HOST, port=PORT, slave_id=SLAVE)
    assert "fan_0" in result  # nosec B101
