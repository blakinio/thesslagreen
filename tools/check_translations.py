"""Check translation files for required option keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANS = ROOT / "custom_components" / "thessla_green_modbus" / "translations"

LANGS = ("en", "pl")

OPTION_KEYS = [
    "force_full_register_list",
    "retry",
    "scan_interval",
    "skip_missing_registers",
    "timeout",
    "deep_scan",
    "max_registers_per_request",
]

OPTION_ERROR_KEYS = [
    'invalid_max_registers_per_request_low',
    'invalid_max_registers_per_request_high',
]


def _load(lang: str) -> dict:
    return json.loads((TRANS / f"{lang}.json").read_text(encoding="utf-8"))


def _check_options(data: dict, lang: str) -> list[str]:
    msg: list[str] = []
    opts = data["options"]["step"]["init"]
    data_keys = set(opts["data"].keys())
    desc_keys = set(opts["data_description"].keys())
    err_keys = set(data["options"].get("error", {}).keys())

    if missing := set(OPTION_KEYS) - data_keys:
        msg.append(f"{lang}: missing option keys: {sorted(missing)}")
    if missing := set(OPTION_KEYS) - desc_keys:
        msg.append(f"{lang}: missing option descriptions: {sorted(missing)}")
    if missing := set(OPTION_ERROR_KEYS) - err_keys:
        msg.append(f"{lang}: missing option errors: {sorted(missing)}")

    if extra := data_keys - set(OPTION_KEYS):
        msg.append(f"{lang}: unused option keys: {sorted(extra)}")
    if extra := desc_keys - set(OPTION_KEYS):
        msg.append(f"{lang}: unused option descriptions: {sorted(extra)}")
    if extra := err_keys - set(OPTION_ERROR_KEYS):
        msg.append(f"{lang}: unused option errors: {sorted(extra)}")

    return msg


def main() -> int:
    problems: list[str] = []
    for lang in LANGS:
        problems.extend(_check_options(_load(lang), lang))

    if problems:
        for p in problems:
            print(p)
        return 1

    print("All translation keys present.")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry
    sys.exit(main())

