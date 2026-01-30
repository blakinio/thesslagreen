"""Tests for async register loader helpers."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.thessla_green_modbus.registers.loader import (
    _REGISTERS_PATH,
    async_compute_file_hash,
    async_load_registers_from_file,
)

pytestmark = pytest.mark.asyncio


class _FakeHass:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def async_add_executor_job(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(((func, *args), kwargs))
        return func(*args, **kwargs)


async def test_async_loader_uses_executor(tmp_path):
    """Ensure async loader reads via the executor helper."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text(), encoding="utf-8")
    mtime = tmp_json.stat().st_mtime

    hass = _FakeHass()
    file_hash = await async_compute_file_hash(hass, tmp_json, mtime)
    registers = await async_load_registers_from_file(
        hass, tmp_json, mtime=mtime, file_hash=file_hash
    )

    assert registers
    assert any(call[0][0] == tmp_json.read_bytes for call in hass.calls)
    assert any(
        call[0][0] == tmp_json.read_text and call[1].get("encoding") == "utf-8"
        for call in hass.calls
    )
