import json
from pathlib import Path

from tools import generate_strings

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / "custom_components" / "thessla_green_modbus" / "strings.json"
EN = ROOT / "custom_components" / "thessla_green_modbus" / "translations" / "en.json"
PL = ROOT / "custom_components" / "thessla_green_modbus" / "translations" / "pl.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_strings_in_sync():
    opts = generate_strings.build()
    strings = _load(STRINGS)
    en = _load(EN)
    pl = _load(PL)

    fields = strings["services"]["set_modbus_parameters"]["fields"]
    assert fields["baud_rate"]["selector"]["select"]["options"] == opts["baud_rate"][0]
    assert fields["parity"]["selector"]["select"]["options"] == opts["parity"][0]
    assert fields["port"]["selector"]["select"]["options"] == opts["port"][0]
    assert fields["stop_bits"]["selector"]["select"]["options"] == opts["stop_bits"][0]
    mode_opts = strings["services"]["set_special_mode"]["fields"]["mode"]["selector"]["select"][
        "options"
    ]
    assert mode_opts == opts["special_mode"][0]

    en_fields = en["services"]["set_modbus_parameters"]["fields"]
    assert en_fields["baud_rate"]["selector"]["select"]["options"] == opts["baud_rate"][0]
    assert en_fields["parity"]["selector"]["select"]["options"] == opts["parity"][0]
    assert en_fields["port"]["selector"]["select"]["options"] == opts["port"][0]
    assert en_fields["stop_bits"]["selector"]["select"]["options"] == opts["stop_bits"][0]
    en_mode = en["services"]["set_special_mode"]["fields"]["mode"]["selector"]["select"]["options"]
    assert en_mode == opts["special_mode"][0]

    pl_fields = pl["services"]["set_modbus_parameters"]["fields"]
    assert pl_fields["baud_rate"]["selector"]["select"]["options"] == opts["baud_rate"][1]
    assert pl_fields["parity"]["selector"]["select"]["options"] == opts["parity"][1]
    assert pl_fields["port"]["selector"]["select"]["options"] == opts["port"][1]
    assert pl_fields["stop_bits"]["selector"]["select"]["options"] == opts["stop_bits"][1]
    pl_mode = pl["services"]["set_special_mode"]["fields"]["mode"]["selector"]["select"]["options"]
    assert pl_mode == opts["special_mode"][1]
