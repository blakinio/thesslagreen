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


def test_no_csv_path_references_outside_tools() -> None:
    """Ensure no CSV file paths are referenced outside ``tools/``."""

    repo_root = Path(__file__).resolve().parent.parent
    tools_dir = repo_root / "tools"
    tests_dir = repo_root / "tests"

    offenders: list[Path] = []
    for py_file in repo_root.rglob("*.py"):
        if tools_dir in py_file.parents or tests_dir in py_file.parents:
            continue
        if ".csv" in py_file.read_text(encoding="utf-8"):
            offenders.append(py_file.relative_to(repo_root))

    assert not offenders, f"CSV paths referenced outside tools/: {offenders}"


def test_modbus_registers_csv_only_used_by_converter() -> None:
    """Ensure ``modbus_registers.csv`` is only referenced by the converter tool."""

    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = repo_root / "tests"
    expected = {Path("tools/convert_registers_csv_to_json.py")}

    consumers: set[Path] = set()
    for py_file in repo_root.rglob("*.py"):
        if tests_dir in py_file.parents:
            continue
        if "modbus_registers.csv" in py_file.read_text(encoding="utf-8"):
            consumers.add(py_file.relative_to(repo_root))

    assert consumers == expected, f"Unexpected consumers: {sorted(consumers)}"

