import csv
import importlib.util
import pathlib

from custom_components.thessla_green_modbus.utils import (
    _decode_bcd_time,
    _decode_register_time,
    _to_snake_case,
    parse_schedule_bcd,
)
from custom_components.thessla_green_modbus.data.modbus_registers import (
    apply_resolution,
    map_enum_value,
    scale_from_raw,
    scale_to_raw,
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


def load_csv_registers() -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.csv")
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Function_Code"]
            if not code or code.startswith("#"):
                continue
            name = _to_snake_case(row["Register_Name"])
            addr = int(row["Address_DEC"])
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


def test_register_definitions_match_csv() -> None:
    csv_coil, csv_discrete, csv_input, csv_holding = load_csv_registers()
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


def test_schedule_bcd_parser() -> None:
    """Ensure schedule parser handles valid and sentinel values."""

    assert parse_schedule_bcd(0x0630) == 390
    assert parse_schedule_bcd(0x8000) is None
    assert parse_schedule_bcd(0x2460) is None


def test_all_registers_have_units() -> None:
    """Ensure every register in the CSV specifies a unit."""
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.csv")
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Function_Code"]
            if not code or code.startswith("#"):
                continue
            assert row["Unit"].strip() != ""  # nosec B101


def test_loader_scaling_and_enum_helpers() -> None:
    """Verify scaling, resolution and enum mapping helpers."""

    # outside_temperature has multiplier/resolution 0.1
    assert scale_from_raw("outside_temperature", 215) == 21.5
    assert scale_to_raw("outside_temperature", 21.5) == 215
    assert apply_resolution("outside_temperature", 21.53) == 21.5

    # bypass register provides enum mapping "0 - OFF; 1 - ON"
    assert map_enum_value("bypass", 1) == "on"
    assert map_enum_value("bypass", "off") == 0
