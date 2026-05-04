"""Tests for coordinator runtime-state helpers."""

from __future__ import annotations

from custom_components.thessla_green_modbus.coordinator.runtime_state import (
    clear_register_failure,
    mark_registers_failed,
)


class _CoordinatorStub:
    pass


def test_mark_registers_failed_creates_and_filters_none() -> None:
    coordinator = _CoordinatorStub()

    mark_registers_failed(coordinator, ["mode", None, "fan_speed"])

    assert coordinator._failed_registers == {"mode", "fan_speed"}


def test_mark_registers_failed_updates_existing_set() -> None:
    coordinator = _CoordinatorStub()
    coordinator._failed_registers = {"mode"}

    mark_registers_failed(coordinator, ["fan_speed", "mode"])

    assert coordinator._failed_registers == {"mode", "fan_speed"}


def test_clear_register_failure_noop_without_state() -> None:
    coordinator = _CoordinatorStub()

    clear_register_failure(coordinator, "mode")

    assert not hasattr(coordinator, "_failed_registers")


def test_clear_register_failure_removes_requested_item() -> None:
    coordinator = _CoordinatorStub()
    coordinator._failed_registers = {"mode", "fan_speed"}

    clear_register_failure(coordinator, "mode")

    assert coordinator._failed_registers == {"fan_speed"}
