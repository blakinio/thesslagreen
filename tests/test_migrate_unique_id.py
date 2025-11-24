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
    assert new_uid == f"{prefix}_{SLAVE}_{REGISTER_NAME}_{REGISTER_ADDRESS}"


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
    assert new_uid == f"{prefix}_{SLAVE}_{REGISTER_NAME}_{REGISTER_ADDRESS}"
