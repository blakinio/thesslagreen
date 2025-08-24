"""Test CSV to JSON register conversion."""

from __future__ import annotations

from pathlib import Path

from tools.convert_registers_csv_to_json import convert


def test_register_csv_conversion(tmp_path: Path) -> None:
    """Ensure the converter output matches the committed JSON file."""

    csv_path = Path("tools") / "modbus_registers.csv"
    output_path = tmp_path / "registers.json"

    convert(csv_path, output_path)

    expected_path = (
        Path("custom_components")
        / "thessla_green_modbus"
        / "registers"
        / "thessla_green_registers_full.json"
    )

    assert output_path.read_text(encoding="utf-8") == expected_path.read_text(
        encoding="utf-8"
    )
