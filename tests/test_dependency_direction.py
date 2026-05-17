"""Test that core/ does not import from coordinator/."""

import ast
import pathlib


def test_core_does_not_import_coordinator():
    base = pathlib.Path("custom_components/thessla_green_modbus/core")
    violations = []
    for py_file in sorted(base.rglob("*.py")):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "coordinator" in node.module:
                        violations.append(f"{py_file}:{node.lineno}: {ast.unparse(node)}")
    assert not violations, "core/ imports coordinator/:\n" + "\n".join(violations)
