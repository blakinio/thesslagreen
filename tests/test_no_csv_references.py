"""Ensure repository has no stray CSV references."""

from __future__ import annotations

from pathlib import Path


def test_no_csv_references() -> None:
    """Fail if any ``*.csv`` files exist outside legacy directories."""

    runtime = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "thessla_green_modbus"
    )
    csv_files = list(runtime.rglob("*.csv"))
    assert not csv_files, f"Unexpected CSV files found: {csv_files}"

