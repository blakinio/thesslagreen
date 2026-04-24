#!/usr/bin/env python3
"""Compare integration register JSON with the vendor reference (airpack4_modbus.json)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "airpack4_modbus.json"
MAIN_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)

KNOWN_EXTRA_PREFIXES = ("alarm", "error", "s_", "e_", "f_")


def _fc_num(key: str) -> int:
    return int(key[2:4])


def _load_reference() -> dict[tuple[int, int], dict]:
    data = json.loads(REF_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for key in (
        "fc01_coils",
        "fc02_discrete_inputs",
        "fc03_holding_registers",
        "fc04_input_registers",
    ):
        fn = _fc_num(key)
        for entry in data[key]["registers"]:
            addr = entry.get("dec")
            if addr is None:
                addr = int(entry["hex"], 16)
            result[(fn, int(addr))] = entry
    return result


def _load_main() -> dict[tuple[int, int], dict]:
    data = json.loads(MAIN_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for r in data["registers"]:
        fn = int(str(r["function"]))
        addr = r.get("address_dec")
        if addr is None:
            addr = int(str(r["address_hex"]), 16)
        result[(fn, int(addr))] = r
    return result


def _is_known_extra(entry: dict) -> bool:
    name = entry.get("name") or ""
    return any(name.startswith(p) for p in KNOWN_EXTRA_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--show-renames", action="store_true")
    args = parser.parse_args()

    ref = _load_reference()
    main = _load_main()

    only_ref = set(ref) - set(main)
    only_main = set(main) - set(ref)
    common = set(ref) & set(main)

    print(f"Reference entries: {len(ref)}")
    print(f"Integration entries: {len(main)}")
    print(f"Common: {len(common)}")
    print(f"Missing from integration: {len(only_ref)}")
    print(f"Extra in integration: {len(only_main)}")

    errors = 0

    if only_ref:
        print("\n!! MISSING from integration (this is a bug) !!")
        for p in sorted(only_ref):
            e = ref[p]
            print(f"  FC{p[0]:02d} 0x{p[1]:04X} ({p[1]:5d}): {e.get('name')!r}")
        errors += len(only_ref)

    unexpected_extra = [p for p in only_main if not _is_known_extra(main[p])]
    if unexpected_extra:
        print("\n?? UNEXPECTED extras in integration (verify with vendor) ??")
        for p in sorted(unexpected_extra):
            e = main[p]
            print(f"  FC{p[0]:02d} 0x{p[1]:04X} ({p[1]:5d}): {e.get('name')!r}")
            print(f"    {str(e.get('description'))[:100]}")
        if args.strict:
            errors += len(unexpected_extra)

    mismatches = []
    for p in common:
        rn = ref[p].get("name")
        mn = main[p].get("name")
        if rn and mn and rn != mn:
            mismatches.append((p, rn, mn))

    print(f"\nName mismatches on common addresses: {len(mismatches)}")
    if args.show_renames:
        for p, rn, mn in sorted(mismatches):
            print(f"  FC{p[0]:02d} 0x{p[1]:04X}: ref={rn!r:45s} -> main={mn!r}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
