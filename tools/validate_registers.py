#!/usr/bin/env python3
"""Validate register definitions in the bundled JSON file."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _prepare_environment() -> None:
    """Add repository root and stub package to ``sys`` modules."""

    sys.path.insert(0, str(ROOT))
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    tg_pkg = types.ModuleType("custom_components.thessla_green_modbus")
    tg_pkg.__path__ = [str(ROOT / "custom_components" / "thessla_green_modbus")]
    sys.modules["custom_components.thessla_green_modbus"] = tg_pkg

    # Stub modules required for importing the registers loader without pulling
    # in the rest of the integration (which would otherwise create circular
    # imports during testing).
    modbus_helpers = types.ModuleType(
        "custom_components.thessla_green_modbus.modbus_helpers"
    )
    modbus_helpers.group_reads = lambda *_, **__: None  # type: ignore
    sys.modules.setdefault(
        "custom_components.thessla_green_modbus.modbus_helpers", modbus_helpers
    )

    schedule_helpers = types.ModuleType(
        "custom_components.thessla_green_modbus.schedule_helpers"
    )
    schedule_helpers.bcd_to_time = lambda *_, **__: None  # type: ignore
    schedule_helpers.time_to_bcd = lambda *_, **__: None  # type: ignore
    sys.modules.setdefault(
        "custom_components.thessla_green_modbus.schedule_helpers", schedule_helpers
    )


def validate(path: Path) -> list[RegisterDefinition]:
    """Validate ``path`` and return the parsed register definitions."""

    _prepare_environment()
    from custom_components.thessla_green_modbus.registers.schema import (
        RegisterDefinition,
        RegisterList,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)

    parsed_list = RegisterList.model_validate(registers)
    return parsed_list.root


def main(path: Path | None = None) -> int:
    """Validate registers file, exiting with ``1`` on error."""

    _prepare_environment()
    from custom_components.thessla_green_modbus.registers.loader import _REGISTERS_PATH

    target = Path(path) if path is not None else _REGISTERS_PATH

    try:
        validate(Path(target))
    except Exception as err:  # pragma: no cover - error path
        print(err)
        raise SystemExit(1)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

