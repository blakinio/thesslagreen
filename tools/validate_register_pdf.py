"""Parse MODBUS register definitions from the official PDF.

This module extracts register metadata such as address, function code, access,
unit, multiplier, resolution and enumerated values from the documentation
PDF.  It is used in tests to verify that the bundled JSON definition is in
sync with the vendor documentation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import re
from io import BytesIO
from urllib.request import urlopen

import pdfplumber

# Official register documentation PDF
PDF_URL = "https://thesslagreen.com/wp-content/uploads/MODBUS_USER_AirPack_Home_08.2021.01.pdf"


def _parse_float(value: str) -> Optional[float]:
    """Convert a numeric string to float, handling commas and blanks."""
    if not value:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _parse_enum(info_lines: List[str]) -> Optional[Dict[str, str]]:
    """Parse enumeration values from info column lines."""
    if not info_lines:
        return None
    text = " ".join(info_lines)
    matches = re.findall(r"(\d+)\s*-\s*([^0-9]+)(?=\s+\d+\s*-|$)", text)
    if not matches:
        return None
    return {num: label.strip() for num, label in matches}


ADDRESS_FIXES = {
    "e200": ("0x20ca", 8394),
    "e201": ("0x20cb", 8395),
}


def _parse_register(rows: List[List[str]], start: int) -> tuple[Dict[str, Any], int]:
    """Parse a single register starting at index ``start``.

    Returns a tuple of (register_dict, next_index).
    """

    cells = rows[start]
    first = cells[0]
    desc = cells[4]
    info_lines: List[str] = []
    if cells[10]:
        info_lines.append(cells[10])
    j = start + 1
    while j < len(rows):
        next_cells = rows[j]
        next_first = next_cells[0]
        if next_first.startswith("0x") or re.match(r"^\d{2} -", next_first):
            break
        if next_cells[4]:
            desc += " " + next_cells[4]
        if next_cells[10]:
            info_lines.append(next_cells[10])
        j += 1

    raw = cells[3].split("\n")[0].strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    addr_hex = first.lower()
    addr_dec = int(addr_hex, 16)
    if name in ADDRESS_FIXES:
        addr_hex, addr_dec = ADDRESS_FIXES[name]

    register = {
        "address_hex": addr_hex,
        "address_dec": addr_dec,
        "name": name,
        "access": cells[2].replace(" ", ""),
        "unit": cells[11] or None,
        "enum": _parse_enum(info_lines),
        "multiplier": _parse_float(cells[8]),
        "resolution": _parse_float(cells[9]),
        "description": " ".join(desc.replace(";", "-").split()),
    }
    return register, j
def parse_pdf_registers(source: str | Path = PDF_URL) -> List[Dict[str, Any]]:
    """Return a list of register dictionaries extracted from the PDF."""

    if str(source).startswith("http"):
        with urlopen(str(source)) as resp:
            pdf_file = BytesIO(resp.read())
        pdf = pdfplumber.open(pdf_file)
    else:
        pdf = pdfplumber.open(Path(source))

    with pdf:
        rows: List[List[str]] = []
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                rows.extend([(c or "").strip() for c in row] for row in table)

    registers: List[Dict[str, Any]] = []
    function: Optional[str] = None
    i = 0
    while i < len(rows):
        cells = rows[i]
        if not any(cells):
            i += 1
            continue

        first = cells[0]
        if re.match(r"^\d{2} -", first):
            function = first.split()[0]
            i += 1
            continue

        if first.startswith("0x"):
            regs_group: List[Dict[str, Any]] = []
            addr_hex = first.lower()
            while i < len(rows):
                sub_cells = rows[i]
                if sub_cells[0].lower() != addr_hex:
                    break
                reg, next_i = _parse_register(rows, i)
                reg["function"] = function
                regs_group.append(reg)
                i = next_i

            if (
                len(regs_group) > 1
                and all(re.fullmatch(r"e\d+", r["name"]) for r in regs_group)
            ):
                start_code = regs_group[0]["name"][1:]
                end_code = regs_group[-1]["name"][1:]
                registers.append(
                    {
                        "function": function,
                        "address_hex": addr_hex,
                        "address_dec": int(addr_hex, 16),
                        "name": f"e{start_code}_e{end_code}",
                        "access": regs_group[0]["access"],
                        "unit": "bitmask",
                        "enum": None,
                        "multiplier": regs_group[0]["multiplier"],
                        "resolution": regs_group[0]["resolution"],
                        "description": f"Flagi błędów E{start_code}-E{end_code}",
                    }
                )
            else:
                registers.extend(regs_group)
            continue

        i += 1

    return registers


if __name__ == "__main__":
    import json
    regs = parse_pdf_registers()
    print(json.dumps(regs[:5], indent=2, ensure_ascii=False))
