import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / "custom_components" / "thessla_green_modbus" / "strings.json"
EN = ROOT / "custom_components" / "thessla_green_modbus" / "translations" / "en.json"
PL = ROOT / "custom_components" / "thessla_green_modbus" / "translations" / "pl.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_strings_in_sync():
    strings = _load(STRINGS)
    en = _load(EN)
    pl = _load(PL)

    fields = strings["services"]["set_modbus_parameters"]["fields"]
    assert set(fields["baud_rate"]) == {"name", "description"}
    assert set(fields["parity"]) == {"name", "description"}
    assert set(fields["port"]) == {"name", "description"}
    assert set(fields["stop_bits"]) == {"name", "description"}
    mode_field = strings["services"]["set_special_mode"]["fields"]["mode"]
    assert set(mode_field) == {"name", "description"}

    en_fields = en["services"]["set_modbus_parameters"]["fields"]
    assert en_fields == fields
    assert en["services"]["set_special_mode"]["fields"]["mode"] == mode_field

    pl_fields = pl["services"]["set_modbus_parameters"]["fields"]
    assert set(pl_fields["baud_rate"]) == {"name", "description"}
    assert set(pl_fields["parity"]) == {"name", "description"}
    assert set(pl_fields["port"]) == {"name", "description"}
    assert set(pl_fields["stop_bits"]) == {"name", "description"}
    assert set(pl["services"]["set_special_mode"]["fields"]["mode"]) == {"name", "description"}
