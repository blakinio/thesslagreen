import csv
import pathlib

from custom_components.thessla_green_modbus.utils import _to_snake_case

CSV_PATH = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.csv")


def _build_map(rows: list[tuple[str, int]]) -> dict[str, int]:
    """Build mapping from register names to addresses with numbering for duplicates."""
    rows.sort(key=lambda item: item[1])
    counts: dict[str, int] = {}
    for name, _ in rows:
        counts[name] = counts.get(name, 0) + 1
    seen: dict[str, int] = {}
    mapping: dict[str, int] = {}
    for name, addr in rows:
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name}_{seen[name]}"
        mapping[name] = addr
    return mapping


def load_csv_registers() -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []

    with CSV_PATH.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            func = row["Function_Code"]
            name = _to_snake_case(row["Register_Name"])
            addr = int(row["Address_DEC"])
            if func == "01":
                coil_rows.append((name, addr))
            elif func == "02":
                discrete_rows.append((name, addr))
            elif func == "04":
                input_rows.append((name, addr))
            elif func == "03":
                holding_rows.append((name, addr))
    return (
        _build_map(coil_rows),
        _build_map(discrete_rows),
        _build_map(input_rows),
        _build_map(holding_rows),
    )


def test_register_map_matches_csv() -> None:
    csv_coil, csv_discrete, csv_input, csv_holding = load_csv_registers()

    from custom_components.thessla_green_modbus import registers as mod

    assert csv_coil == mod.COIL_REGISTERS  # nosec B101
    assert csv_discrete == mod.DISCRETE_INPUT_REGISTERS  # nosec B101
    assert csv_input == mod.INPUT_REGISTERS  # nosec B101
    assert csv_holding == mod.HOLDING_REGISTERS  # nosec B101
