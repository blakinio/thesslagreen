#!/usr/bin/env python3
"""Validate register addresses against JSON definition."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, Set

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "registers" / "thessla_green_registers_full.json"
REGISTERS_PATH = ROOT / "custom_components" / "thessla_green_modbus" / "registers.py"

FUNCTION_MAP = {
    "COIL_REGISTERS": "01",
    "DISCRETE_INPUT_REGISTERS": "02",
    "INPUT_REGISTERS": "04",
    "HOLDING_REGISTERS": "03",
}


def parse_json(path: Path) -> tuple[Dict[str, Dict[str, Set[int]]], Dict[str, Set[int]]]:
    """Return grouped and total addresses from the JSON file."""
    groups: Dict[str, Dict[str, Set[int]]] = {}
    totals: Dict[str, Set[int]] = {}
    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)
    for reg in registers:
        code = str(reg["function"]).zfill(2)
        name = str(reg["name"]).strip()
        addr = int(reg["address_dec"])
        groups.setdefault(code, {}).setdefault(name, set()).add(addr)
        totals.setdefault(code, set()).add(addr)
    return groups, totals


def parse_registers(path: Path) -> Dict[str, Set[int]]:
    """Return a mapping of dictionary name to addresses from registers.py."""
    tree = ast.parse(path.read_text())
    result: Dict[str, Set[int]] = {}
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and target.id in FUNCTION_MAP:
            name = target.id
            values = set()
            dict_node = value
            if isinstance(dict_node, ast.Dict):
                for val in dict_node.values:
                    if isinstance(val, ast.Constant) and isinstance(val.value, int):
                        values.add(val.value)
            result[name] = values
    return result


def main() -> None:
    json_groups, json_totals = parse_json(JSON_PATH)
    py_addrs = parse_registers(REGISTERS_PATH)
    ok = True
    for dict_name, func_code in FUNCTION_MAP.items():
        py_set = py_addrs.get(dict_name, set())
        missing: list[int] = []
        for addr_set in json_groups.get(func_code, {}).values():
            if addr_set.isdisjoint(py_set):
                missing.extend(sorted(addr_set))
        extra = py_set - json_totals.get(func_code, set())
        if missing or extra:
            ok = False
            if missing:
                print(f"{dict_name} missing addresses: {missing}")
            if extra:
                print(f"{dict_name} extra addresses: {sorted(extra)}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
