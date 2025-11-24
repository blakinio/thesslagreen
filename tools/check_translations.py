"""Check translation files for required option keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANS = ROOT / "custom_components" / "thessla_green_modbus" / "translations"
STRINGS = ROOT / "custom_components" / "thessla_green_modbus" / "strings.json"

BASE_LANG = "en"
LANGS = (BASE_LANG, "pl")

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
    "max_registers_range",
]


def _load(lang: str) -> dict:
    return json.loads((TRANS / f"{lang}.json").read_text(encoding="utf-8"))


def _collect_keys(data: dict | list, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(data, dict):
        for key, val in data.items():
            path = f"{prefix}.{key}" if prefix else key
            keys.add(path)
            keys |= _collect_keys(val, path)
    elif isinstance(data, list):
        for item in data:
            keys |= _collect_keys(item, prefix)
    return keys


def _check_strings(data: dict, strings: dict, lang: str) -> list[str]:
    msg: list[str] = []
    data_keys = _collect_keys(data)
    str_keys = _collect_keys(strings)
    if missing := str_keys - data_keys:
        msg.append(f"{lang}: missing keys compared to strings.json: {sorted(missing)}")
    if extra := data_keys - str_keys:
        msg.append(f"{lang}: extra keys compared to strings.json: {sorted(extra)}")
    return msg


def _check_section(
    data_keys: set[str],
    ref_keys: set[str],
    lang: str,
    label: str,
) -> list[str]:
    msg: list[str] = []
    if missing := ref_keys - data_keys:
        msg.append(f"{lang}: missing {label}: {sorted(missing)}")
    if extra := data_keys - ref_keys:
        msg.append(f"{lang}: unused {label}: {sorted(extra)}")
    return msg


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


def _check_diagnostics(data: dict, ref: dict, lang: str) -> list[str]:
    data_keys = set(data.get("diagnostics", {}).keys())
    ref_keys = set(ref.get("diagnostics", {}).keys())
    return _check_section(data_keys, ref_keys, lang, "diagnostic keys")


def _check_errors(data: dict, ref: dict, lang: str) -> list[str]:
    data_keys = set(data.get("config", {}).get("error", {}).keys())
    ref_keys = set(ref.get("config", {}).get("error", {}).keys())
    return _check_section(data_keys, ref_keys, lang, "error keys")


def main() -> int:
    problems: list[str] = []
    ref = _load(BASE_LANG)
    strings = json.loads(STRINGS.read_text(encoding="utf-8"))
    for lang in LANGS:
        data = _load(lang)
        problems.extend(_check_options(data, lang))
        problems.extend(_check_strings(data, strings, lang))
        problems.extend(_check_diagnostics(data, ref, lang))
        problems.extend(_check_errors(data, ref, lang))

    if problems:
        for p in problems:
            print(p)
        return 1

    print("All translation keys present.")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry
    sys.exit(main())
