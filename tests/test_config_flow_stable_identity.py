"""Stable config-entry identity and connection-match regression tests."""

from custom_components.thessla_green_modbus._config_flow.entry import (
    build_connection_match,
    build_stable_unique_id,
)
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
)
from homeassistant.const import CONF_HOST, CONF_PORT


def test_stable_unique_id_uses_confirmed_serial() -> None:
    assert build_stable_unique_id({"serial_number": " AP4-00123 "}) == "serial:ap4-00123"


def test_stable_unique_id_rejects_placeholder_identity() -> None:
    for value in (None, "", "Unknown", "N/A", "0"):
        assert build_stable_unique_id({"serial_number": value}) is None


def test_tcp_connection_identity_is_match_data_not_unique_id() -> None:
    data = {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
        CONF_HOST: "airpack.local",
        CONF_PORT: 8899,
        CONF_SLAVE_ID: 10,
    }
    assert build_connection_match(data) == data
    assert build_stable_unique_id(data) is None


def test_rtu_connection_identity_is_match_data_not_unique_id() -> None:
    data = {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
        CONF_SERIAL_PORT: "/dev/serial/by-id/airpack",
        CONF_SLAVE_ID: 10,
    }
    assert build_connection_match(data) == data
    assert build_stable_unique_id(data) is None
