"""Tests for coordinator device-info/scan helper extraction."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from custom_components.thessla_green_modbus._coordinator_device_info import (
    run_device_scan,
    warn_missing_device_info,
)


class _DummyScanner:
    def __init__(self) -> None:
        self.closed = False

    async def scan_device(self) -> dict[str, str]:
        return {"model": "X"}

    async def close(self) -> None:
        self.closed = True


def test_run_device_scan_applies_result_and_closes() -> None:
    scanner = _DummyScanner()
    applied: dict[str, str] = {}

    async def _create() -> _DummyScanner:
        return scanner

    def _apply(result: dict[str, str]) -> None:
        applied.update(result)

    run_logger = logging.getLogger("test.run_device_scan")
    asyncio.run(
        run_device_scan(create_scanner=_create, apply_scan_result=_apply, logger=run_logger)
    )

    assert applied == {"model": "X"}
    assert scanner.closed is True


def test_warn_missing_device_info_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING")
    cfg = SimpleNamespace(host="127.0.0.1", port=502, slave_id=1)

    warn_missing_device_info(
        device_info={"model": "Unknown", "firmware": "Unknown"},
        config=cfg,
        device_name="Thessla",
        logger=logging.getLogger("test.warn_missing"),
        unknown_model="Unknown",
    )

    assert any("missing model and firmware" in rec.getMessage().lower() for rec in caplog.records)
