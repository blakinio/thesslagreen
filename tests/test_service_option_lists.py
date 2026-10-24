from custom_components.thessla_green_modbus import options
from custom_components.thessla_green_modbus.services import schema

OPTION_LIST_NAMES = (
    "SPECIAL_MODE_OPTIONS",
    "DAYS_OF_WEEK",
    "PERIODS",
    "BYPASS_MODES",
    "GWC_MODES",
    "FILTER_TYPES",
    "RESET_TYPES",
    "MODBUS_PORTS",
    "MODBUS_BAUD_RATES",
    "MODBUS_PARITY",
    "MODBUS_STOP_BITS",
)


async def test_setup_options_fills_the_lists_importers_already_hold():
    held = {name: getattr(options, name) for name in OPTION_LIST_NAMES}

    await options.async_setup_options()

    for name, value in held.items():
        assert getattr(options, name) is value, name
        assert value, name


async def test_service_schemas_accept_options_loaded_after_import():
    await options.async_setup_options()

    reset_filters = schema.RESET_FILTERS_SCHEMA(
        {
            "entity_id": "climate.thesslagreen",
            "filter_type": "thessla_green_modbus.filter_type_cleanpad_pure",
        }
    )
    reset_settings = schema.RESET_SETTINGS_SCHEMA(
        {"entity_id": "climate.thesslagreen", "reset_type": options.RESET_TYPES[0]}
    )

    assert reset_filters["filter_type"] == "thessla_green_modbus.filter_type_cleanpad_pure"
    assert reset_settings["reset_type"] == options.RESET_TYPES[0]
