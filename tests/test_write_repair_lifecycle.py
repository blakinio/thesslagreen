"""Regression tests for write-failure repair issue lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.coordinator.write_path import (
    run_multi_register_write_attempts,
    run_single_write_attempts,
)
from custom_components.thessla_green_modbus.core.write_path import SingleWritePlan
from custom_components.thessla_green_modbus.repairs import (
    clear_write_failure_issue,
    create_write_failure_issue,
    write_failure_issue_id,
)


def test_write_failure_issue_id_is_entry_scoped() -> None:
    entry = MagicMock()
    entry.entry_id = "abc123"
    assert write_failure_issue_id(entry) == "modbus_write_failed_abc123"
    assert write_failure_issue_id(None) == "modbus_write_failed"


def test_create_and_clear_write_failure_issue() -> None:
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "abc123"

    with (
        patch(
            "custom_components.thessla_green_modbus.repairs.ir.async_create_issue"
        ) as create_issue,
        patch(
            "custom_components.thessla_green_modbus.repairs.ir.async_delete_issue"
        ) as delete_issue,
    ):
        create_write_failure_issue(hass, entry, register="mode")
        clear_write_failure_issue(hass, entry)

    create_issue.assert_called_once()
    args, kwargs = create_issue.call_args
    assert args[2] == "modbus_write_failed_abc123"
    assert kwargs["translation_key"] == "modbus_write_failed"
    assert kwargs["is_fixable"] is False
    assert kwargs["is_persistent"] is False
    assert kwargs["data"] == {"register": "mode"}
    delete_issue.assert_called_once_with(hass, "thessla_green_modbus", "modbus_write_failed_abc123")


@pytest.mark.asyncio
async def test_final_single_write_failure_creates_repair_issue() -> None:
    coordinator = MagicMock()
    coordinator.device_client.retry = 1
    coordinator._execute_single_register_write_attempt = AsyncMock(return_value=("error", False))
    coordinator._handle_write_response_failure.return_value = False
    plan = SingleWritePlan(
        register_name="mode",
        address=4208,
        encoded_values=None,
        scalar_value=1,
        original_value=1,
    )

    with patch(
        "custom_components.thessla_green_modbus.coordinator.write_path._create_write_repair"
    ) as create_repair:
        success, refresh = await run_single_write_attempts(coordinator, MagicMock(), plan, True)

    assert success is False
    assert refresh is False
    create_repair.assert_called_once_with(coordinator, "mode")


@pytest.mark.asyncio
async def test_successful_single_write_clears_repair_issue() -> None:
    coordinator = MagicMock()
    coordinator.device_client.retry = 1
    coordinator._execute_single_register_write_attempt = AsyncMock(return_value=("ok", True))
    coordinator._handle_successful_single_register_write.return_value = True
    plan = SingleWritePlan(
        register_name="mode",
        address=4208,
        encoded_values=None,
        scalar_value=1,
        original_value=1,
    )

    with patch(
        "custom_components.thessla_green_modbus.coordinator.write_path._clear_write_repair"
    ) as clear_repair:
        success, refresh = await run_single_write_attempts(coordinator, MagicMock(), plan, True)

    assert success is True
    assert refresh is True
    clear_repair.assert_called_once_with(coordinator)


@pytest.mark.asyncio
async def test_final_multi_write_failure_creates_repair_issue() -> None:
    coordinator = MagicMock()
    coordinator.device_client.retry = 1
    coordinator._plan_multi_register_chunks.return_value = [(100, [1, 2])]
    coordinator._execute_multi_register_chunks = AsyncMock(return_value=("error", False))
    coordinator._handle_write_response_failure.return_value = False

    with patch(
        "custom_components.thessla_green_modbus.coordinator.write_path._create_write_repair"
    ) as create_repair:
        success, refresh = await run_multi_register_write_attempts(
            coordinator, 100, [1, 2], True, True
        )

    assert success is False
    assert refresh is False
    create_repair.assert_called_once_with(coordinator, "100")
