"""Split register loader tests."""

import json
from pathlib import Path


def _add_desc(reg: dict) -> dict:
    return {
        **reg,
        "description": reg.get("description", "desc"),
        "description_en": reg.get("description_en", "desc"),
    }


def _write(path: Path, regs: list[dict]) -> None:
    path.write_text(json.dumps({"registers": [_add_desc(r) for r in regs]}))
