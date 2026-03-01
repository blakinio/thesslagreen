import ast
import json
import re
import sys
import types
from importlib import resources
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "thessla_green_modbus"

with open(ROOT / "translations" / "en.json", encoding="utf-8") as f:
    EN = json.load(f)
with open(ROOT / "translations" / "pl.json", encoding="utf-8") as f:
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
                    for k, v in zip(val.keys, val.values, strict=False):
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
const.STATE_UNAVAILABLE = "unavailable"


class UnitOfTemperature:  # pragma: no cover - enum stub
    CELSIUS = "°C"


class UnitOfVolumeFlowRate:  # pragma: no cover - enum stub
    CUBIC_METERS_PER_HOUR = "m³/h"


class UnitOfElectricPotential:  # pragma: no cover - enum stub
    VOLT = "V"


const.UnitOfTemperature = UnitOfTemperature
const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate
const.UnitOfElectricPotential = UnitOfElectricPotential

network_mod = types.ModuleType("homeassistant.util.network")
network_mod.is_host_valid = lambda host: True
sys.modules["homeassistant.util.network"] = network_mod

sensor_mod = types.ModuleType("homeassistant.components.sensor")


class SensorEntity:  # pragma: no cover - simple stub
    pass


class SensorDeviceClass:  # pragma: no cover - enum stub
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"
    POWER = "power"
    ENERGY = "energy"


class SensorStateClass:  # pragma: no cover - enum stub
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


sensor_mod.SensorEntity = SensorEntity
sensor_mod.SensorDeviceClass = SensorDeviceClass
sensor_mod.SensorStateClass = SensorStateClass
sys.modules["homeassistant.components.sensor"] = sensor_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

SENSOR_KEYS = _load_translation_keys(ROOT / "entity_mappings.py", "SENSOR_ENTITY_MAPPINGS") + [
    "error_codes"
]
BINARY_KEYS = _load_translation_keys(ROOT / "entity_mappings.py", "BINARY_SENSOR_ENTITY_MAPPINGS")
SWITCH_KEYS = _load_keys(ROOT / "entity_mappings.py", "SWITCH_ENTITY_MAPPINGS") + _load_keys(
    ROOT / "const.py", "SPECIAL_FUNCTION_MAP"
)
SELECT_KEYS = _load_keys(ROOT / "entity_mappings.py", "SELECT_ENTITY_MAPPINGS")
NUMBER_KEYS = _load_keys(ROOT / "entity_mappings.py", "NUMBER_ENTITY_MAPPINGS")
# Error/status code translations are not currently enforced
CODE_KEYS: list[str] = []

# Extend BINARY_KEYS with dynamically generated alarm/error/s_*/e_* registers
# and extend SENSOR_KEYS with dynamically generated BCD time registers (schedule_,
# airing_*, gwc regen, etc.).  These are not in the static dicts above but ARE
# written into the translation files.
import json as _json  # noqa: E402  (already imported at module level as json)
import re as _re  # noqa: E402

_REGISTERS_JSON = ROOT / "registers" / "thessla_green_registers_full.json"

try:
    from custom_components.thessla_green_modbus.utils import (  # noqa: E402
        BCD_TIME_PREFIXES,
        _normalise_name,
    )

    _reg_data = _json.loads(_REGISTERS_JSON.read_text(encoding="utf-8"))
    for _r in _reg_data.get("registers", []):
        _name = _normalise_name(_r.get("name") or "")
        if not _name:
            continue
        if _name in {"alarm", "error"} or _re.match(r"^[se]_", _name):
            if _name not in BINARY_KEYS:
                BINARY_KEYS.append(_name)
        if any(_name.startswith(_p) for _p in BCD_TIME_PREFIXES):
            if _name not in SENSOR_KEYS:
                SENSOR_KEYS.append(_name)
except Exception:  # pragma: no cover - best-effort extension
    pass
ISSUE_KEYS = ["modbus_write_failed"]

OPTION_KEYS = [
    "enable_device_scan",
    "force_full_register_list",
    "log_level",
    "retry",
    "safe_scan",
    "scan_interval",
    "skip_missing_registers",
    "timeout",
    "deep_scan",
    "max_registers_per_request",
]

OPTION_ERROR_KEYS = [
    "max_registers_range",
]


class Loader(yaml.SafeLoader):
    pass


def _include(loader, node):
    file_path = ROOT / loader.construct_scalar(node)
    with open(file_path, encoding="utf-8") as f:
        return yaml.load(f, Loader)  # nosec B506


Loader.add_constructor("!include", _include)

with open(ROOT / "services.yaml", encoding="utf-8") as f:
    SERVICES = yaml.load(f, Loader=Loader).keys()  # nosec B506


def _assert_keys(trans, entity_type, keys):
    section = trans["entity"][entity_type]
    missing = [k for k in keys if k not in section]
    extra = [k for k in section if k not in keys]
    assert not missing, f"Missing {entity_type} translations: {missing}"  # nosec B101
    assert not extra, f"Extra {entity_type} translations: {extra}"  # nosec B101


def _assert_code_keys(trans, keys):
    section = trans.get("codes")
    if not section:
        return
    missing = [k for k in keys if k not in section]
    assert not missing, f"Missing code translations: {missing}"  # nosec B101


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
        if "codes" in trans:
            _assert_code_keys(trans, CODE_KEYS)
        _assert_issue_keys(trans, ISSUE_KEYS)
        missing_services = [s for s in SERVICES if s not in trans["services"]]
        assert (
            not missing_services
        ), f"Missing service translations: {missing_services}"  # nosec B101
        opts = trans["options"]["step"]["init"]
        missing_opts = [k for k in OPTION_KEYS if k not in opts["data"]]
        assert not missing_opts, f"Missing option translations: {missing_opts}"  # nosec B101
        missing_desc = [k for k in OPTION_KEYS if k not in opts["data_description"]]
        assert not missing_desc, f"Missing option descriptions: {missing_desc}"  # nosec B101
        missing_err = [k for k in OPTION_ERROR_KEYS if k not in trans["options"].get("error", {})]
        assert not missing_err, f"Missing option error translations: {missing_err}"  # nosec B101


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
    new_binary_keys = ["water_removal_active"]
    new_sensor_keys = ["constant_flow_active"]
    for trans in (EN, PL):
        for key in new_keys:
            assert key in trans["entity"]["sensor"]
            assert key in trans["entity"]["number"]
        for key in new_binary_keys:
            assert key in trans["entity"]["binary_sensor"]
        for key in new_sensor_keys:
            assert key in trans["entity"]["sensor"]


def _to_snake(name: str) -> str:
    """Convert camelCase names to snake_case without typo correction."""
    name = name.replace("-", "_").replace(" ", "_")
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def test_register_names_match_translations() -> None:
    """Ensure register names used in mappings exist and have translations."""

    reg_path = resources.files("custom_components.thessla_green_modbus.registers").joinpath(
        "thessla_green_registers_full.json"
    )
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    registers = data["registers"]

    fn_map = {
        "01": "coil_registers",
        "02": "discrete_input_registers",
        "03": "holding_registers",
        "04": "input_registers",
    }
    reg_names: dict[str, set[str]] = {v: set() for v in fn_map.values()}
    for reg in registers:
        func = str(reg["function"]).zfill(2)
        if func in fn_map:
            reg_names[fn_map[func]].add(_to_snake(reg["name"]))

    source = (ROOT / "entity_mappings.py").read_text()
    tree = ast.parse(source)

    vars_to_entity = {
        "BINARY_SENSOR_ENTITY_MAPPINGS": "binary_sensor",
        "SWITCH_ENTITY_MAPPINGS": "switch",
        "SELECT_ENTITY_MAPPINGS": "select",
        "NUMBER_ENTITY_MAPPINGS": "number",
    }

    ignore = {"hood_output"}
    for var, entity_type in vars_to_entity.items():
        for node in tree.body:
            if isinstance(node, ast.Assign | ast.AnnAssign):
                target = node.targets[0] if isinstance(node, ast.Assign) else node.target
                if (
                    isinstance(target, ast.Name)
                    and target.id == var
                    and isinstance(node.value, ast.Dict)
                ):
                    for key_node, val_node in zip(node.value.keys, node.value.values, strict=False):
                        if isinstance(key_node, ast.Constant) and isinstance(val_node, ast.Dict):
                            name = key_node.value
                            reg_type = None
                            trans_key = name
                            for k2, v2 in zip(val_node.keys, val_node.values, strict=False):
                                if isinstance(k2, ast.Constant):
                                    if k2.value == "register_type" and isinstance(v2, ast.Constant):
                                        reg_type = v2.value
                                    elif k2.value == "translation_key" and isinstance(
                                        v2, ast.Constant
                                    ):
                                        trans_key = v2.value

                            if reg_type in reg_names and name not in ignore:
                                assert (
                                    _to_snake(name) in reg_names[reg_type]
                                ), f"Missing register definition for {name}"
                            assert trans_key in EN["entity"][entity_type]
                            assert trans_key in PL["entity"][entity_type]
                            break
                    break
