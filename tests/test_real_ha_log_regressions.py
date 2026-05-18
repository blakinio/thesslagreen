"""Regression tests for real HA log issues fixed in this branch.

Covers four scenarios:
1. No blocking translation I/O on event loop during async setup.
2. Cached-scan setup does NOT fail connection test via direct client.
3. Unsupported firmware registers (input 0-15, exception code 2) log at DEBUG, not WARNING.
4. Unknown model/firmware is handled as non-fatal (DEBUG only).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# 1. Blocking I/O guard (async_setup_entity_mappings must use executor)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_blocking_translation_open_during_async_setup() -> None:
    """async_setup_entity_mappings must not call Path.open on the event-loop thread."""
    import asyncio
    import threading
    from pathlib import Path
    from unittest.mock import patch

    import custom_components.thessla_green_modbus.mappings as em
    from custom_components.thessla_green_modbus.mappings._helpers import (
        _load_translation_keys,
        _number_translation_keys,
    )

    _number_translation_keys.cache_clear()
    _load_translation_keys.cache_clear()

    event_loop_thread = threading.current_thread()
    blocking_opens: list[str] = []
    original_open = Path.open

    def _tracking_open(self: Path, *args: object, **kwargs: object):  # type: ignore[override]
        if threading.current_thread() is event_loop_thread:
            blocking_opens.append(str(self))
        return original_open(self, *args, **kwargs)

    mock_hass = MagicMock()

    async def _executor_job(fn, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args)

    mock_hass.async_add_executor_job = _executor_job

    with patch.object(Path, "open", _tracking_open):
        await em.async_setup_entity_mappings(hass=mock_hass)

    assert not blocking_opens, "Path.open was called from event-loop thread: " + ", ".join(
        blocking_opens
    )

    _number_translation_keys.cache_clear()
    _load_translation_keys.cache_clear()
    em._run_build_entity_mappings()


# ---------------------------------------------------------------------------
# 2. Connection test succeeds when direct client is used (no transport)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_test_succeeds_with_direct_client(caplog) -> None:
    """run_connection_test must not raise when transport is None but client exists."""
    from custom_components.thessla_green_modbus.core.connection_test import run_connection_test

    mock_client = MagicMock()
    mock_client.connected = True

    async def _ensure():
        pass

    with caplog.at_level(logging.DEBUG):
        await run_connection_test(
            ensure_connection=_ensure,
            get_transport=lambda: None,
            get_client=lambda: mock_client,
            slave_id=1,
            test_addresses=[0, 1, 2],
            is_cancelled_error=lambda _: False,
            logger=logging.getLogger("test"),
        )

    assert "Connection test successful (direct client)" in caplog.text


@pytest.mark.asyncio
async def test_connection_test_fails_when_transport_and_client_both_none() -> None:
    """run_connection_test must raise when both transport and client are None."""
    from custom_components.thessla_green_modbus.core.connection_test import run_connection_test
    from pymodbus.exceptions import ConnectionException

    async def _ensure():
        pass

    with pytest.raises(ConnectionException):
        await run_connection_test(
            ensure_connection=_ensure,
            get_transport=lambda: None,
            get_client=lambda: None,
            slave_id=1,
            test_addresses=[0],
            is_cancelled_error=lambda _: False,
            logger=logging.getLogger("test"),
        )


# ---------------------------------------------------------------------------
# 3. Exception code 2 on input registers 0-15 logs at DEBUG, not WARNING
# ---------------------------------------------------------------------------


def test_firmware_register_exception_code2_no_warning(caplog) -> None:
    """Exception code 2 on input registers 0-15 must not produce a WARNING log."""
    from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
    from custom_components.thessla_green_modbus.scanner.io_read import (
        _handle_register_error_response,
    )

    scanner = ThesslaGreenDeviceScanner("1.2.3.4", 502, 10)

    with caplog.at_level(logging.WARNING):
        _handle_register_error_response(
            scanner,
            register_type="input_registers",
            start=0,
            end=15,
            address=0,
            count=16,
            code=2,
        )

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warnings, (
        f"Unexpected WARNING for firmware register range: {[r.message for r in warnings]}"
    )


def test_non_firmware_register_exception_code2_warns(caplog) -> None:
    """Exception code 2 on input registers outside 0-15 still produces a WARNING."""
    from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
    from custom_components.thessla_green_modbus.scanner.io_read import (
        _handle_register_error_response,
    )

    scanner = ThesslaGreenDeviceScanner("1.2.3.4", 502, 10)

    with caplog.at_level(logging.WARNING):
        _handle_register_error_response(
            scanner,
            register_type="input_registers",
            start=16,
            end=30,
            address=16,
            count=15,
            code=2,
        )

    assert any(r.levelno >= logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# 4. Unknown model/firmware is non-fatal (logs at DEBUG only)
# ---------------------------------------------------------------------------


def test_unknown_model_firmware_no_warning(caplog) -> None:
    """warn_missing_device_info must log at DEBUG, not WARNING, for unknown values."""
    from custom_components.thessla_green_modbus.coordinator.device_info import (
        warn_missing_device_info,
    )

    config = MagicMock()
    config.host = "192.168.1.1"
    config.port = 502
    config.slave_id = 1

    with caplog.at_level(logging.WARNING):
        warn_missing_device_info(
            device_info={"model": "Unknown", "firmware": "Unknown"},
            config=config,
            device_name="ThesslaGreen",
            logger=logging.getLogger("test"),
            unknown_model="Unknown",
        )

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warnings, (
        f"Unexpected WARNING for unknown device info: {[r.message for r in warnings]}"
    )


def test_known_model_firmware_no_log(caplog) -> None:
    """warn_missing_device_info must be silent when both model and firmware are known."""
    from custom_components.thessla_green_modbus.coordinator.device_info import (
        warn_missing_device_info,
    )

    config = MagicMock()
    config.host = "192.168.1.1"
    config.port = 502
    config.slave_id = 1

    with caplog.at_level(logging.DEBUG):
        warn_missing_device_info(
            device_info={"model": "ThesslaGreen X", "firmware": "4.85.0"},
            config=config,
            device_name="ThesslaGreen",
            logger=logging.getLogger("test"),
            unknown_model="Unknown",
        )

    assert not caplog.records
