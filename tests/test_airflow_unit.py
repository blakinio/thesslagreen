import sys
import types
from unittest.mock import MagicMock

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
const.PERCENTAGE = "%"
const.STATE_UNAVAILABLE = "unavailable"


class UnitOfVolumeFlowRate:  # pragma: no cover - enum stub
    CUBIC_METERS_PER_HOUR = "m³/h"


const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate

from homeassistant.const import PERCENTAGE, UnitOfVolumeFlowRate  # noqa: E402

from custom_components.thessla_green_modbus.const import (  # noqa: E402
    AIRFLOW_UNIT_M3H,
    AIRFLOW_UNIT_PERCENTAGE,
    CONF_AIRFLOW_UNIT,
)
from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity  # noqa: E402
from custom_components.thessla_green_modbus.entity_mappings import (  # noqa: E402
    SENSOR_ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.sensor import ThesslaGreenSensor  # noqa: E402


def _make_coordinator(unit):
    coord = MagicMock()
    coord.host = "1.2.3.4"
    coord.port = 502
    coord.slave_id = 10
    coord.device_info = {}
    coord.get_device_info.return_value = {}
    coord.entry = MagicMock()
    coord.entry.options = {CONF_AIRFLOW_UNIT: unit}
    coord.data = {}
    return coord


def test_unique_id_same_for_all_units():
    coord = _make_coordinator(AIRFLOW_UNIT_PERCENTAGE)
    entity = ThesslaGreenEntity(coord, "supply_flow_rate", 274)
    uid_percentage = entity.unique_id

    coord.entry.options[CONF_AIRFLOW_UNIT] = AIRFLOW_UNIT_M3H
    entity = ThesslaGreenEntity(coord, "supply_flow_rate", 274)
    address = 274
    entity = ThesslaGreenEntity(coord, "supply_flow_rate", address)
    uid_percentage = entity.unique_id

    coord.entry.options[CONF_AIRFLOW_UNIT] = AIRFLOW_UNIT_M3H
    entity = ThesslaGreenEntity(coord, "supply_flow_rate", address)
    uid_m3h = entity.unique_id

    assert uid_percentage == uid_m3h  # nosec


def test_sensor_converts_to_percentage():
    coord = _make_coordinator(AIRFLOW_UNIT_PERCENTAGE)
    coord.data.update({"supply_flow_rate": 150, "nominal_supply_air_flow": 300})
    sensor_def = SENSOR_ENTITY_MAPPINGS["supply_flow_rate"]
    address = 274
    sensor = ThesslaGreenSensor(coord, "supply_flow_rate", address, sensor_def)
    assert sensor.native_unit_of_measurement == PERCENTAGE
    assert sensor.native_value == 50


def test_sensor_reports_m3h_by_default():
    coord = _make_coordinator(AIRFLOW_UNIT_M3H)
    coord.data.update({"supply_flow_rate": 150})
    sensor_def = SENSOR_ENTITY_MAPPINGS["supply_flow_rate"]
    address = 274
    sensor = ThesslaGreenSensor(coord, "supply_flow_rate", address, sensor_def)
    assert sensor.native_unit_of_measurement == UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    assert sensor.native_value == 150
