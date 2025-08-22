#!/usr/bin/env python3
"""Compile all modules to detect syntax errors."""
from __future__ import annotations

import pathlib
import py_compile
import sys


def main() -> int:
    base_dir = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "thessla_green_modbus"
    errors: list[str] = []
    for module in base_dir.rglob("*.py"):
        try:
            py_compile.compile(module, doraise=True)
        except py_compile.PyCompileError as err:
            errors.append(str(err))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
