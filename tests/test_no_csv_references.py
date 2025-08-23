"""Ensure repository has no stray CSV references."""

from __future__ import annotations

from pathlib import Path
import tomllib


def test_no_csv_references() -> None:
    """Fail if any ``*.csv`` files exist outside legacy directories."""

    runtime = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "thessla_green_modbus"
    )
    csv_files = list(runtime.rglob("*.csv"))
    assert not csv_files, f"Unexpected CSV files found: {csv_files}"


def test_modbus_registers_csv_excluded_from_package_data() -> None:
    """Ensure tools CSV file is excluded from built packages."""

    repo_root = Path(__file__).resolve().parent.parent
    assert (repo_root / "tools" / "modbus_registers.csv").exists()

    manifest_lines = (
        repo_root / "MANIFEST.in"
    ).read_text(encoding="utf-8").splitlines()
    assert "global-exclude *.csv" in [line.strip() for line in manifest_lines]

    pyproject_data = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    exclude_patterns = (
        pyproject_data.get("tool", {})
        .get("setuptools", {})
        .get("exclude-package-data", {})
        .get("*", [])
    )
    assert "*.csv" in exclude_patterns

