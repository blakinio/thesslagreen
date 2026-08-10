from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected exactly one match for {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "custom_components/thessla_green_modbus/core/capabilities_mixin.py",
    "        if any(v is None for v in (raw_yymm, raw_ddtt, raw_ggmm, raw_sscc)):\n"
    "            return None\n",
    "        if (\n"
    "            raw_yymm is None\n"
    "            or raw_ddtt is None\n"
    "            or raw_ggmm is None\n"
    "            or raw_sscc is None\n"
    "        ):\n"
    "            return None\n",
)

replace(
    "custom_components/thessla_green_modbus/coordinator/coordinator.py",
    "    _reauth_scheduled: bool\n",
    "    _device_client: ThesslaGreenDeviceClient\n"
    "    _reauth_scheduled: bool\n",
)

# The first pass removes itself and the temporary workflow from the working tree.
# Remove this second-pass helper as well so no verification scaffolding remains.
Path(__file__).unlink()
