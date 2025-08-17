import ast
import json
import sys
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "thessla_green_modbus"

with open(ROOT / "translations" / "en.json", "r", encoding="utf-8") as f:
    EN = json.load(f)
with open(ROOT / "translations" / "pl.json", "r", encoding="utf-8") as f:
    PL = json.load(f)


def _load_translation_keys(file: Path, var_name: str):
    tree = ast.parse(file.read_text(), filename=str(file))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            continue
        if (
            isinstance(target, ast.Name)
            and target.id == var_name
            and isinstance(node.value, ast.Dict)
        ):
            keys = []
            for val in node.value.values:
                if isinstance(val, ast.Dict):
                    for k, v in zip(val.keys, val.values):
                        if (
                            isinstance(k, ast.Constant)
                            and k.value == "translation_key"
                            and isinstance(v, ast.Constant)
                        ):
                            keys.append(v.value)
            return keys
    return []


def _load_keys(file: Path, var_name: str):
    tree = ast.parse(file.read_text(), filename=str(file))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            continue
        if (
            isinstance(target, ast.Name)
            and target.id == var_name
            and isinstance(node.value, ast.Dict)
        ):
            return [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    return []


# Import sensor module to obtain translation keys
const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
const.PERCENTAGE = "%"


class UnitOfTemperature:  # pragma: no cover - enum stub
    CELSIUS = "°C"


class UnitOfVolumeFlowRate:  # pragma: no cover - enum stub
    CUBIC_METERS_PER_HOUR = "m³/h"


class UnitOfElectricPotential:  # pragma: no cover - enum stub
    VOLT = "V"


const.UnitOfTemperature = UnitOfTemperature
const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate
const.UnitOfElectricPotential = UnitOfElectricPotential

sensor_mod = types.ModuleType("homeassistant.components.sensor")


class SensorEntity:  # pragma: no cover - simple stub
    pass


class SensorDeviceClass:  # pragma: no cover - enum stub
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"


class SensorStateClass:  # pragma: no cover - enum stub
    MEASUREMENT = "measurement"


sensor_mod.SensorEntity = SensorEntity
sensor_mod.SensorDeviceClass = SensorDeviceClass
sensor_mod.SensorStateClass = SensorStateClass
sys.modules["homeassistant.components.sensor"] = sensor_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

from custom_components.thessla_green_modbus.sensor import SENSOR_DEFINITIONS

SENSOR_KEYS = [v["translation_key"] for v in SENSOR_DEFINITIONS.values()]
BINARY_KEYS = _load_translation_keys(ROOT / "binary_sensor.py", "BINARY_SENSOR_DEFINITIONS")
SWITCH_KEYS = _load_keys(ROOT / "switch.py", "SWITCH_ENTITIES")
SELECT_KEYS = _load_keys(ROOT / "select.py", "SELECT_DEFINITIONS")
NUMBER_KEYS = _load_keys(ROOT / "entity_mappings.py", "NUMBER_ENTITY_MAPPINGS")
REGISTER_KEYS = _load_keys(ROOT / "registers.py", "HOLDING_REGISTERS")
# Error codes translations are not currently enforced
ERROR_KEYS: list[str] = []
ISSUE_KEYS = ["modbus_write_failed"]


class Loader(yaml.SafeLoader):
    pass


def _include(loader, node):
    file_path = ROOT / loader.construct_scalar(node)
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader)  # nosec B506


Loader.add_constructor("!include", _include)

with open(ROOT / "services.yaml", "r", encoding="utf-8") as f:
    SERVICES = yaml.load(f, Loader=Loader).keys()  # nosec B506


def _assert_keys(trans, entity_type, keys):
    section = trans["entity"][entity_type]
    missing = [k for k in keys if k not in section]
    extra = [k for k in section if k not in keys]
    assert not missing, f"Missing {entity_type} translations: {missing}"  # nosec B101
    assert not extra, f"Extra {entity_type} translations: {extra}"  # nosec B101


def _assert_error_keys(trans, keys):
    section = trans.get("errors")
    if not section:
        return
    missing = [k for k in keys if k not in section]
    assert not missing, f"Missing error translations: {missing}"  # nosec B101


def _assert_issue_keys(trans, keys):
    section = trans.get("issues", {})
    missing = [k for k in keys if k not in section]
    assert not missing, f"Missing issue translations: {missing}"  # nosec B101
    for key in keys:
        issue = section[key]
        assert "title" in issue, f"Missing issue title: {key}"  # nosec B101
        assert "description" in issue, f"Missing issue description: {key}"  # nosec B101


def test_translation_keys_present():
    for trans in (EN, PL):
        section = trans["entity"]["sensor"]
        missing = [k for k in SENSOR_KEYS if k not in section]
        assert not missing, f"Missing sensor translations: {missing}"  # nosec B101
        _assert_keys(trans, "binary_sensor", BINARY_KEYS)
        _assert_keys(trans, "switch", SWITCH_KEYS)
        _assert_keys(trans, "select", SELECT_KEYS)
        if NUMBER_KEYS:
            _assert_keys(trans, "number", NUMBER_KEYS)
        if "errors" in trans:
            _assert_error_keys(trans, ERROR_KEYS)
        _assert_issue_keys(trans, ISSUE_KEYS)
        missing_services = [s for s in SERVICES if s not in trans["services"]]
        assert (
            not missing_services
        ), f"Missing service translations: {missing_services}"  # nosec B101


def test_translation_structures_match():
    def compare_dict(en, pl, path=""):
        assert set(en.keys()) == set(  # nosec B101
            pl.keys()
        ), f"Mismatch at {path}: {set(en.keys()) ^ set(pl.keys())}"
        for key in en:
            if isinstance(en[key], dict):
                compare_dict(en[key], pl[key], f"{path}{key}.")

    compare_dict(EN, PL)


def test_new_translation_keys_present():
    """Ensure translations exist for newly added registers."""
    new_keys = [
        "max_supply_air_flow_rate",
        "max_exhaust_air_flow_rate",
        "nominal_supply_air_flow",
        "nominal_exhaust_air_flow",
        "bypass_off",
        "air_flow_rate_manual",
        "air_flow_rate_temporary_2",
    ]
    new_binary_keys = ["constant_flow_active", "water_removal_active"]
    for trans in (EN, PL):
        for key in new_keys:
            assert key in trans["entity"]["sensor"]
            assert key in trans["entity"]["number"]
        for key in new_binary_keys:
            assert key in trans["entity"]["binary_sensor"]
