from custom_components.thessla_green_modbus.coordinator.register_processing import (
    create_consecutive_groups,
)


def test_create_consecutive_groups_empty():
    assert create_consecutive_groups({}) == []
