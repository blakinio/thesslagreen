"""Tests for register file parsing helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from custom_components.thessla_green_modbus.registers.parse_file_helpers import (
    async_read_registers_json,
    read_registers_json,
)


def test_read_registers_json_file_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Register definition file missing"):
        read_registers_json(tmp_path / "missing.json")


@pytest.mark.asyncio
async def test_async_read_registers_json_file_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Register definition file missing"):
        await async_read_registers_json(None, tmp_path / "missing.json")
