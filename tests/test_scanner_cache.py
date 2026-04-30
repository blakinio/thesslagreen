"""Scanner register cache/runtime coverage tests."""


def test_build_register_maps_direct():
    from custom_components.thessla_green_modbus.scanner.register_map_runtime import (
        build_register_maps,
    )

    build_register_maps()
    from custom_components.thessla_green_modbus.scanner.core import REGISTER_DEFINITIONS

    assert isinstance(REGISTER_DEFINITIONS, dict)
