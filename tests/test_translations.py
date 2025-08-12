import json
import yaml
import ast
from pathlib import Path

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
        if isinstance(target, ast.Name) and target.id == var_name and isinstance(node.value, ast.Dict):
            return [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    return []


SENSOR_KEYS = _load_keys(ROOT / "sensor.py", "SENSOR_DEFINITIONS")
BINARY_KEYS = _load_keys(ROOT / "binary_sensor.py", "BINARY_SENSOR_DEFINITIONS")
SWITCH_KEYS = _load_keys(ROOT / "switch.py", "SWITCH_ENTITIES")
SELECT_KEYS = _load_keys(ROOT / "select.py", "SELECT_DEFINITIONS")
NUMBER_KEYS = _load_keys(ROOT / "const.py", "NUMBER_ENTITY_MAPPINGS")

SERVICES = yaml.safe_load((ROOT / "services.yaml").read_text()).keys()


def _assert_keys(trans, entity_type, keys):
    section = trans["entity"][entity_type]
    missing = [k for k in keys if k not in section]
    assert not missing, f"Missing {entity_type} translations: {missing}"


def test_translation_keys_present():
    for trans in (EN, PL):
        _assert_keys(trans, "sensor", SENSOR_KEYS)
        _assert_keys(trans, "binary_sensor", BINARY_KEYS)
        _assert_keys(trans, "switch", SWITCH_KEYS)
        _assert_keys(trans, "select", SELECT_KEYS)
        _assert_keys(trans, "number", NUMBER_KEYS)
        missing_services = [s for s in SERVICES if s not in trans["services"]]
        assert not missing_services, f"Missing service translations: {missing_services}"


def test_translation_structures_match():
    def compare_dict(en, pl, path=""):
        assert set(en.keys()) == set(pl.keys()), f"Mismatch at {path}: {set(en.keys()) ^ set(pl.keys())}"
        for key in en:
            if isinstance(en[key], dict):
                compare_dict(en[key], pl[key], f"{path}{key}.")
    compare_dict(EN, PL)

