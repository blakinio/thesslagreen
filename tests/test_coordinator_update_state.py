from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.thessla_green_modbus.coordinator.update_state import (
    begin_update_cycle,
    finish_update_cycle,
)


def test_begin_update_cycle_returns_existing_data_when_already_running() -> None:
    coordinator = MagicMock()
    coordinator._update_in_progress = True
    coordinator.data = {"temperature": 21}

    result = begin_update_cycle(coordinator)

    assert result == {"temperature": 21}


def test_begin_update_cycle_initializes_runtime_flags() -> None:
    coordinator = MagicMock()
    coordinator._update_in_progress = False
    coordinator._failed_registers = {"legacy"}

    result = begin_update_cycle(coordinator)

    assert result is None
    assert coordinator._update_in_progress is True
    assert coordinator._failed_registers == set()


def test_finish_update_cycle_resets_runtime_flag() -> None:
    coordinator = MagicMock()
    coordinator._update_in_progress = True

    finish_update_cycle(coordinator)

    assert coordinator._update_in_progress is False
