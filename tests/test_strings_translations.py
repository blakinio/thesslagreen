import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "thessla_green_modbus"


def _collect_keys(obj, prefix=""):
    keys = set()
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            keys.add(path)
            keys |= _collect_keys(val, path)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _collect_keys(item, prefix)
    return keys


def test_strings_and_translations_match() -> None:
    strings = json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))
    ref_keys = _collect_keys(strings)
    for lang in ("en", "pl"):
        data = json.loads((ROOT / "translations" / f"{lang}.json").read_text(encoding="utf-8"))
        data_keys = _collect_keys(data)
        missing = ref_keys - data_keys
        extra = data_keys - ref_keys
        assert not missing and not extra, (
            f"{lang}: missing keys {sorted(missing)}, extra keys {sorted(extra)}"
        )
