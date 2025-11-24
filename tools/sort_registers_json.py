"""Sort the canonical JSON register file by function and address."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)


def sort_registers_json(path: Path = DEFAULT_JSON) -> None:
    """Sort registers in ``path`` by function then decimal address."""

    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data["registers"]
    sorted_regs = sorted(
        registers,
        key=lambda r: (int(str(r["function"])), int(r["address_dec"])),
    )
    if registers != sorted_regs:
        data["registers"] = sorted_regs
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sort register JSON by function and decimal address.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_JSON),
        help="Path to the register JSON file.",
    )
    args = parser.parse_args()
    sort_registers_json(Path(args.path))


if __name__ == "__main__":
    main()
