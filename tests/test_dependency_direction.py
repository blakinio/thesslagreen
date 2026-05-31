"""Test that dependency direction rules are respected across all packages.

Rules verified here:
- core/     must not import coordinator/ (at any level, including TYPE_CHECKING)
- transport/ must not import coordinator/ or platform modules
- scanner/  must not import coordinator/ or platform modules
"""

from __future__ import annotations

import ast
import pathlib

_PKG = pathlib.Path("custom_components/thessla_green_modbus")

_PLATFORM_MODULES = {
    "binary_sensor",
    "button",
    "climate",
    "fan",
    "number",
    "select",
    "sensor",
    "switch",
    "text",
    "time",
}


def _collect_imports(base: pathlib.Path) -> list[tuple[pathlib.Path, int, str]]:
    """Return (file, lineno, unparsed-import) for every import in *base*."""
    results = []
    for py_file in sorted(base.rglob("*.py")):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        results.extend(
            (py_file, node.lineno, node.module, ast.unparse(node))
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
    return results


def test_core_does_not_import_coordinator():
    base = _PKG / "core"
    violations = []
    for py_file, lineno, module, unparsed in _collect_imports(base):
        if "coordinator" in module:
            violations.append(f"{py_file}:{lineno}: {unparsed}")
    assert not violations, "core/ imports coordinator/:\n" + "\n".join(violations)


def test_transport_does_not_import_coordinator_or_platforms():
    base = _PKG / "transport"
    violations = []
    for py_file, lineno, module, unparsed in _collect_imports(base):
        pkg = _PKG.name
        if f"{pkg}.coordinator" in module:
            violations.append(f"{py_file}:{lineno}: {unparsed}")
        violations.extend(
            f"{py_file}:{lineno}: {unparsed}"
            for plat in _PLATFORM_MODULES
            if module.endswith(f".{plat}") or module == f"{pkg}.{plat}"
        )
    assert not violations, "transport/ imports coordinator or platform:\n" + "\n".join(violations)


def test_scanner_does_not_import_coordinator_or_platforms():
    base = _PKG / "scanner"
    violations = []
    for py_file, lineno, module, unparsed in _collect_imports(base):
        pkg = _PKG.name
        if f"{pkg}.coordinator" in module:
            violations.append(f"{py_file}:{lineno}: {unparsed}")
        violations.extend(
            f"{py_file}:{lineno}: {unparsed}"
            for plat in _PLATFORM_MODULES
            if module.endswith(f".{plat}") or module == f"{pkg}.{plat}"
        )
    assert not violations, "scanner/ imports coordinator or platform:\n" + "\n".join(violations)
