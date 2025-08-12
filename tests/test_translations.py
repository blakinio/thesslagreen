import ast
import json
from pathlib import Path

import yaml

from custom_components.thessla_green_modbus.const import SPECIAL_FUNCTION_MAP

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "thessla_green_modbus"

with open(ROOT / "translations" / "en.json", "r", encoding="utf-8") as f:
    EN = json.load(f)
with open(ROOT / "translations" / "pl.json", "r", encoding="utf-8") as f:
    PL = json.load(f)


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


SENSOR_KEYS = _load_keys(ROOT / "sensor.py", "SENSOR_DEFINITIONS")
BINARY_KEYS = _load_keys(ROOT / "binary_sensor.py", "BINARY_SENSOR_DEFINITIONS")
SWITCH_KEYS = ["on_off_panel_mode"] + list(SPECIAL_FUNCTION_MAP.keys())
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


SENSOR_KEYS = _load_translation_keys(ROOT / "sensor.py", "SENSOR_DEFINITIONS")
BINARY_KEYS = _load_translation_keys(ROOT / "binary_sensor.py", "BINARY_SENSOR_DEFINITIONS")
SWITCH_KEYS = _load_keys(ROOT / "switch.py", "SWITCH_ENTITIES")
SELECT_KEYS = _load_keys(ROOT / "select.py", "SELECT_DEFINITIONS")
NUMBER_KEYS = _load_keys(ROOT / "entity_mappings.py", "NUMBER_ENTITY_MAPPINGS")
REGISTER_KEYS = _load_keys(ROOT / "registers.py", "HOLDING_REGISTERS")
# Error codes translations are not currently enforced
ERROR_KEYS: list[str] = []


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
    assert not missing, f"Missing {entity_type} translations: {missing}"  # nosec B101


def _assert_error_keys(trans, keys):
    section = trans.get("errors")
    if not section:
        return
    missing = [k for k in keys if k not in section]
    assert not missing, f"Missing error translations: {missing}"  # nosec B101


def test_translation_keys_present():
    for trans in (EN, PL):
        _assert_keys(trans, "sensor", SENSOR_KEYS)
        _assert_keys(trans, "binary_sensor", BINARY_KEYS)
        _assert_keys(trans, "switch", SWITCH_KEYS)
        _assert_keys(trans, "select", SELECT_KEYS)
        _assert_keys(trans, "number", NUMBER_KEYS)
        if "errors" in trans:
            _assert_error_keys(trans, ERROR_KEYS)
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
