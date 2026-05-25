"""Compare AirPack4 vendor reference (airpack4_modbus.json) with integration register map.

Outputs:
  docs/airpack4_vendor_reference_coverage.md
  docs/airpack4_vendor_reference_coverage.json

Usage:
  python tools/compare_airpack4_vendor_coverage.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENDOR_PATH = ROOT / "airpack4_modbus.json"
INTEGRATION_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)
OUT_MD = ROOT / "docs" / "airpack4_vendor_reference_coverage.md"
OUT_JSON = ROOT / "docs" / "airpack4_vendor_reference_coverage.json"

# Vendor names of dangerous / action registers
DANGEROUS_VENDOR_NAMES: set[str] = {
    "filterChange",
    "lockPass1",
    "lockPass2",
    "lockFlag",
    "hard_reset_settings",
    "hard_reset_schedule",
    "uart0Id",
    "uart0Baud",
    "uart0Parity",
    "uart0Stop",
    "uart1Id",
    "uart1Baud",
    "uart1Parity",
    "uart1Stop",
    "deviceName",
    "deviceName_2",
    "deviceName_3",
    "deviceName_4",
    "deviceName_5",
    "deviceName_6",
    "deviceName_7",
    "deviceName_8",
    "access_level",
    "configuration_mode",
}

KNOWN_EXTRA_WHITELIST: dict[tuple[int, int], str] = {
    (4, 0x0017): "heating_temperature — TH sensor on AirPack4 h/v units",
    (4, 0x012A): "water_removal_active — HEWR procedure flag, series 4",
    (3, 0x20FA): "firmware-observed alarm: filter replacement required (unit without pressure switch); kept as real-device extra",
    (3, 0x20FC): "firmware-observed alarm: filter replacement required (unit with pressure switch); kept as real-device extra",
}

KNOWN_EXTRA_PREFIXES = ("alarm", "error", "s_", "e_", "f_")

FC_KEYS = (
    "fc01_coils",
    "fc02_discrete_inputs",
    "fc03_holding_registers",
    "fc04_input_registers",
)


def fc_num(key: str) -> int:
    return int(key[2:4])


def fc_label(fn: int) -> str:
    return f"FC{fn:02d}"


def load_vendor(path: Path) -> dict[tuple[int, int], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for key in FC_KEYS:
        fn = fc_num(key)
        for entry in data[key]["registers"]:
            addr = entry.get("dec")
            if addr is None:
                addr = int(entry["hex"], 16)
            result[(fn, int(addr))] = entry
    return result


def load_integration(path: Path) -> dict[tuple[int, int], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for r in data["registers"]:
        fn = int(str(r["function"]))
        addr = r.get("address_dec")
        if addr is None:
            addr = int(str(r["address_hex"]), 16)
        result[(fn, int(addr))] = r
    return result


def load_vendor_counts(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: len(data[key]["registers"]) for key in FC_KEYS}


def load_vendor_duplicates(path: Path) -> list[dict[str, Any]]:
    """Find duplicate addresses within each FC section in the vendor file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    duplicates: list[dict[str, Any]] = []
    for key in FC_KEYS:
        fn = fc_num(key)
        seen: dict[int, dict[str, Any]] = {}
        for entry in data[key]["registers"]:
            addr = entry.get("dec")
            if addr is None:
                addr = int(entry["hex"], 16)
            addr = int(addr)
            if addr in seen:
                duplicates.append(
                    {
                        "fc": fn,
                        "address_dec": addr,
                        "address_hex": hex(addr),
                        "first": seen[addr].get("name"),
                        "duplicate": entry.get("name"),
                    }
                )
            else:
                seen[addr] = entry
    return duplicates


def classify_name_mismatch(vendor_name: str, integration_name: str) -> str:
    """Classify a name mismatch as typo_normalization, legacy_stable, or probable_mismatch."""

    # Typo normalization: camelCase -> snake_case, or minor punctuation differences
    def to_snake(s: str) -> str:
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
        s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
        return s.lower().replace("-", "_").replace(" ", "_")

    vn_snake = to_snake(vendor_name)
    # Check if integration name is just a snake_case/normalized form of vendor name
    if vn_snake == integration_name:
        return "typo_normalization"
    # Check if integration name is a substring match or similar
    vn_stripped = vn_snake.replace("_", "")
    in_stripped = integration_name.replace("_", "")
    if vn_stripped == in_stripped:
        return "typo_normalization"
    # Legacy stable: integration name has a legacy prefix/suffix pattern
    if integration_name.startswith(("s_", "e_", "f_", "alarm_", "error_")):
        return "legacy_stable"
    # Otherwise flag as probable_mismatch
    return "probable_mismatch"


def build_report(
    vendor: dict[tuple[int, int], dict[str, Any]],
    integration: dict[tuple[int, int], dict[str, Any]],
    vendor_counts: dict[str, int],
    vendor_duplicates: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_keys = sorted(set(vendor) - set(integration))
    extra_keys = sorted(set(integration) - set(vendor))
    common_keys = sorted(set(vendor) & set(integration))

    # Missing
    missing: list[dict[str, Any]] = []
    for key in missing_keys:
        vr = vendor[key]
        name = vr.get("name", "")
        # Risk classification
        if name in DANGEROUS_VENDOR_NAMES or any(name.startswith("deviceName") for _ in [1]):
            risk = "DANGEROUS"
        elif vr.get("access", "R") == "RW":
            risk = "writable"
        else:
            risk = "read_only"
        missing.append(
            {
                "fc": key[0],
                "fc_label": fc_label(key[0]),
                "address_dec": key[1],
                "address_hex": hex(key[1]),
                "vendor_name": name,
                "access": vr.get("access", "R"),
                "description": vr.get("description", ""),
                "risk": risk,
            }
        )

    # Extras
    extras: list[dict[str, Any]] = []
    for key in extra_keys:
        ir = integration[key]
        name = ir.get("name", "")
        if key in KNOWN_EXTRA_WHITELIST:
            reason = KNOWN_EXTRA_WHITELIST[key]
            known = True
        elif any(name.startswith(p) for p in KNOWN_EXTRA_PREFIXES):
            reason = f"known prefix '{next(p for p in KNOWN_EXTRA_PREFIXES if name.startswith(p))}'"
            known = True
        else:
            reason = "UNKNOWN — requires investigation"
            known = False
        extras.append(
            {
                "fc": key[0],
                "fc_label": fc_label(key[0]),
                "address_dec": key[1],
                "address_hex": hex(key[1]),
                "integration_name": name,
                "known_intentional": known,
                "reason": reason,
            }
        )

    # Name mismatches
    mismatches: list[dict[str, Any]] = []
    for key in common_keys:
        vr = vendor[key]
        ir = integration[key]
        vname = vr.get("name", "")
        iname = ir.get("name", "")
        if vname != iname:
            classification = classify_name_mismatch(vname, iname)
            mismatches.append(
                {
                    "fc": key[0],
                    "fc_label": fc_label(key[0]),
                    "address_dec": key[1],
                    "address_hex": hex(key[1]),
                    "vendor_name": vname,
                    "integration_name": iname,
                    "classification": classification,
                }
            )

    # Dangerous register list
    dangerous: list[dict[str, Any]] = []
    for key, vr in vendor.items():
        vname = vr.get("name", "")
        if vname in DANGEROUS_VENDOR_NAMES or (
            vname.startswith("deviceName") and len(vname) > len("deviceName") - 1
        ):
            ir = integration.get(key)
            dangerous.append(
                {
                    "fc": key[0],
                    "fc_label": fc_label(key[0]),
                    "address_dec": key[1],
                    "address_hex": hex(key[1]),
                    "vendor_name": vname,
                    "integration_name": ir.get("name") if ir else None,
                    "access": vr.get("access", "R"),
                    "in_integration": ir is not None,
                }
            )
    dangerous.sort(key=lambda x: (x["fc"], x["address_dec"]))

    # Per-FC counts
    fc_counts: dict[str, dict[str, int]] = {}
    for key_str, count in vendor_counts.items():
        fn = fc_num(key_str)
        label = fc_label(fn)
        int_count = sum(1 for k in integration if k[0] == fn)
        vendor_count = count
        fc_counts[label] = {
            "vendor": vendor_count,
            "integration": int_count,
        }

    mismatch_by_class: dict[str, int] = {}
    for m in mismatches:
        c = m["classification"]
        mismatch_by_class[c] = mismatch_by_class.get(c, 0) + 1

    return {
        "summary": {
            "vendor_total": len(vendor),
            "integration_total": len(integration),
            "common": len(common_keys),
            "missing_from_integration": len(missing),
            "extras_in_integration": len(extras),
            "name_mismatches": len(mismatches),
            "mismatch_by_class": mismatch_by_class,
            "vendor_duplicates": len(vendor_duplicates),
        },
        "fc_counts": fc_counts,
        "missing": missing,
        "extras": extras,
        "name_mismatches": mismatches,
        "vendor_duplicates": vendor_duplicates,
        "dangerous_registers": dangerous,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    s = report["summary"]
    lines.append("# AirPack4 Vendor Reference Coverage Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Vendor total registers | {s['vendor_total']} |")
    lines.append(f"| Integration total registers | {s['integration_total']} |")
    lines.append(f"| Common (vendor ∩ integration) | {s['common']} |")
    lines.append(f"| Missing from integration | {s['missing_from_integration']} |")
    lines.append(f"| Extras in integration (not in vendor) | {s['extras_in_integration']} |")
    lines.append(f"| Name mismatches (same address, different name) | {s['name_mismatches']} |")
    lines.append(f"| Vendor duplicate addresses | {s['vendor_duplicates']} |")
    lines.append("")

    lines.append("## Counts per Function Code")
    lines.append("")
    lines.append("| FC | Vendor | Integration |")
    lines.append("|----|--------|-------------|")
    for label, counts in sorted(report["fc_counts"].items()):
        lines.append(f"| {label} | {counts['vendor']} | {counts['integration']} |")
    lines.append("")

    lines.append("## Missing from Integration")
    lines.append("")
    if report["missing"]:
        lines.append(
            "| FC | Address (hex) | Address (dec) | Vendor name | Access | Risk | Description |"
        )
        lines.append(
            "|-----|--------------|--------------|-------------|--------|------|-------------|"
        )
        for m in report["missing"]:
            desc = m["description"].replace("|", "\\|")[:60]
            lines.append(
                f"| {m['fc_label']} | {m['address_hex']} | {m['address_dec']} "
                f"| {m['vendor_name']} | {m['access']} | {m['risk']} | {desc} |"
            )
    else:
        lines.append("None — all vendor registers are present in the integration.")
    lines.append("")

    lines.append("## Extras in Integration (not in vendor reference)")
    lines.append("")
    if report["extras"]:
        lines.append(
            "| FC | Address (hex) | Address (dec) | Integration name | Known intentional | Reason |"
        )
        lines.append(
            "|-----|--------------|--------------|------------------|-------------------|--------|"
        )
        lines.extend(
            f"| {e['fc_label']} | {e['address_hex']} | {e['address_dec']} "
            f"| {e['integration_name']} | {'yes' if e['known_intentional'] else 'NO'} | {e['reason']} |"
            for e in report["extras"]
        )
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Name Mismatches (same address, different name)")
    lines.append("")
    mc = report["summary"]["mismatch_by_class"]
    lines.append(
        f"Total: {report['summary']['name_mismatches']} mismatches — "
        f"typo_normalization: {mc.get('typo_normalization', 0)}, "
        f"legacy_stable: {mc.get('legacy_stable', 0)}, "
        f"probable_mismatch: {mc.get('probable_mismatch', 0)}"
    )
    lines.append("")
    lines.append(
        "> **Policy**: Integration register names are stable legacy names. "
        "They MUST NOT be renamed as that would break existing entity IDs, "
        "unique IDs, and service names. Name mismatches are expected and benign."
    )
    lines.append("")
    if report["name_mismatches"]:
        lines.append("| FC | Address (hex) | Vendor name | Integration name | Classification |")
        lines.append("|-----|--------------|-------------|-----------------|----------------|")
        lines.extend(
            f"| {m['fc_label']} | {m['address_hex']} | {m['vendor_name']} "
            f"| {m['integration_name']} | {m['classification']} |"
            for m in report["name_mismatches"][:50]
        )
        if len(report["name_mismatches"]) > 50:
            lines.append(
                f"| ... | ... | ... | ... | *(+{len(report['name_mismatches']) - 50} more)* |"
            )
    lines.append("")

    lines.append("## Vendor Duplicate Addresses")
    lines.append("")
    if report["vendor_duplicates"]:
        lines.append("| FC | Address (hex) | Address (dec) | First name | Duplicate name |")
        lines.append("|-----|--------------|--------------|------------|----------------|")
        lines.extend(
            f"| FC{d['fc']:02d} | {d['address_hex']} | {d['address_dec']} "
            f"| {d['first']} | {d['duplicate']} |"
            for d in report["vendor_duplicates"]
        )
    else:
        lines.append("None — no duplicate addresses in vendor reference.")
    lines.append("")

    lines.append("## Dangerous / Action Registers")
    lines.append("")
    lines.append(
        "These registers require elevated caution: they can reset device state, "
        "lock the device, or change communication parameters."
    )
    lines.append("")
    lines.append(
        "| FC | Address (hex) | Vendor name | Integration name | Access | In integration |"
    )
    lines.append("|-----|--------------|-------------|-----------------|--------|----------------|")
    for d in report["dangerous_registers"]:
        iname = d["integration_name"] or "—"
        present = "yes" if d["in_integration"] else "**NO**"
        lines.append(
            f"| {d['fc_label']} | {d['address_hex']} | {d['vendor_name']} "
            f"| {iname} | {d['access']} | {present} |"
        )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    vendor = load_vendor(VENDOR_PATH)
    integration = load_integration(INTEGRATION_PATH)
    vendor_counts = load_vendor_counts(VENDOR_PATH)
    vendor_duplicates = load_vendor_duplicates(VENDOR_PATH)

    report = build_report(vendor, integration, vendor_counts, vendor_duplicates)

    OUT_MD.write_text(render_markdown(report), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    s = report["summary"]
    print("AirPack4 Vendor Reference Coverage")
    print("=" * 40)
    print(f"  Vendor total:          {s['vendor_total']}")
    print(f"  Integration total:     {s['integration_total']}")
    print(f"  Common:                {s['common']}")
    print(f"  Missing:               {s['missing_from_integration']}")
    print(f"  Extras:                {s['extras_in_integration']}")
    print(f"  Name mismatches:       {s['name_mismatches']}")
    print(f"  Vendor duplicates:     {s['vendor_duplicates']}")
    print()
    if report["missing"]:
        print("Missing registers:")
        for m in report["missing"]:
            print(
                f"  [{m['fc_label']}] {m['address_hex']:>8} ({m['address_dec']:>6}) "
                f"{m['vendor_name']:<30} {m['access']:<3} risk={m['risk']}"
            )
    else:
        print("No missing registers.")
    print()
    print("Output written to:")
    print(f"  {OUT_MD}")
    print(f"  {OUT_JSON}")


if __name__ == "__main__":
    main()
