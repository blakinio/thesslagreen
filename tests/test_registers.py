import json
import importlib.util
import pathlib

from custom_components.thessla_green_modbus.utils import (
    _decode_bcd_time,
    _decode_register_time,
    _to_snake_case,
)


def _build_register_map(rows: list[tuple[str, int]]) -> dict[str, int]:
    rows.sort(key=lambda r: r[1])
    counts: dict[str, int] = {}
    for name, _ in rows:
        counts[name] = counts.get(name, 0) + 1
    seen: dict[str, int] = {}
    result: dict[str, int] = {}
    for name, addr in rows:
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name}_{seen[name]}"
        result[name] = addr
    return result


def load_json_registers() -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.json")
    with csv_path.open(encoding="utf-8") as f:
        data = json.load(f)
    for row in data.get("registers", []):
        code = row.get("function")
        name = _to_snake_case(row.get("name", ""))
        name = {
            "date_time_rrmm": "date_time",
            "date_time_ddtt": "date_time",
            "date_time_ggmm": "date_time",
            "date_time_sscc": "date_time",
            "lock_date_rrmm": "lock_date",
            "lock_date_ddtt": "lock_date",
            "lock_date_ggmm": "lock_date",
            "lock_date_rr": "lock_date",
            "lock_date_mm": "lock_date",
            "lock_date_dd": "lock_date",
        }.get(name, name)
        addr = int(row.get("address_dec", 0))
        if code == "01":
            coil_rows.append((name, addr))
        elif code == "02":
            discrete_rows.append((name, addr))
        elif code == "04":
            input_rows.append((name, addr))
        elif code == "03":
            holding_rows.append((name, addr))
    return (
        _build_register_map(coil_rows),
        _build_register_map(discrete_rows),
        _build_register_map(input_rows),
        _build_register_map(holding_rows),
    )


def load_module_registers() -> (
    tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]
):
    module_path = pathlib.Path("custom_components/thessla_green_modbus/registers.py")
    spec = importlib.util.spec_from_file_location("registers", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load registers module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        module.COIL_REGISTERS,
        module.DISCRETE_INPUT_REGISTERS,
        module.INPUT_REGISTERS,
        module.HOLDING_REGISTERS,
    )


def test_register_definitions_match_json() -> None:
    csv_coil, csv_discrete, csv_input, csv_holding = load_json_registers()
    mod_coil, mod_discrete, mod_input, mod_holding = load_module_registers()
    assert csv_coil == mod_coil  # nosec B101
    assert csv_discrete == mod_discrete  # nosec B101
    assert csv_input == mod_input  # nosec B101
    assert csv_holding == mod_holding  # nosec B101
    assert len(mod_input) == 26  # nosec B101
    assert len(mod_holding) == 281  # nosec B101


def test_time_decoding_helpers() -> None:
    """Ensure time decoding helpers map to minutes since midnight."""
    assert _decode_register_time(0x081E) == 510
    assert _decode_register_time(0x1234) == 1132
    assert _decode_register_time(0x2460) is None
    assert _decode_register_time(0x0960) is None

    assert _decode_bcd_time(0x1234) == 754
    assert _decode_bcd_time(0x0800) == 480
    assert _decode_bcd_time(0x2460) is None
    assert _decode_bcd_time(2400) is None


def test_all_registers_have_units() -> None:
    """Ensure every register in the JSON specifies a unit."""
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.json")
    with csv_path.open(encoding="utf-8") as f:
        data = json.load(f)
    for row in data.get("registers", []):
        code = row.get("function")
        if code not in {"01", "02", "03", "04"}:
            continue
        assert row.get("unit") not in (None, "")  # nosec B101
