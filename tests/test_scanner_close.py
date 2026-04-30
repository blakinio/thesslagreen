import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


def test_async_setup_closes_scanner():
    """Ensure scanner is closed after async_setup."""

    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator.from_params(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        scanner = AsyncMock()
        scanner.scan_device.return_value = {
            "available_registers": {
                "input_registers": set(),
                "holding_registers": set(),
                "coil_registers": set(),
                "discrete_inputs": set(),
            },
            "device_info": {},
            "capabilities": {},
        }
        scanner.close = AsyncMock()

        with (
            patch(
                "custom_components.thessla_green_modbus.coordinator.coordinator.ThesslaGreenDeviceScanner.create",
                AsyncMock(return_value=scanner),
            ),
            patch.object(coordinator, "_test_connection", AsyncMock()),
        ):
            result = await coordinator.async_setup()

        assert result is True
        scanner.close.assert_awaited_once()

    asyncio.run(run_test())


def test_async_setup_cancel_mid_scan(caplog):
    """Device scan cancellation closes scanner without errors."""

    async def run_test(caplog):
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator.from_params(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        scan_event = asyncio.Event()
        scanner = AsyncMock()

        async def scan_side_effect():
            await scan_event.wait()

        scanner.scan_device.side_effect = scan_side_effect
        scanner.close = AsyncMock()

        with (
            patch(
                "custom_components.thessla_green_modbus.coordinator.coordinator.ThesslaGreenDeviceScanner.create",
                AsyncMock(return_value=scanner),
            ),
            patch.object(coordinator, "_test_connection", AsyncMock()),
        ):
            caplog.set_level(logging.DEBUG)
            setup_task = asyncio.create_task(coordinator.async_setup())
            await asyncio.sleep(0)
            setup_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await setup_task

        scanner.close.assert_awaited_once()
        assert not any(record.levelno >= logging.ERROR for record in caplog.records)
        assert "Device scan cancelled" in caplog.text

    asyncio.run(run_test(caplog))


def test_disconnect_closes_client():
    """Ensure _disconnect awaits client.close."""

    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator.from_params(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        client = AsyncMock()
        coordinator.client = client

        await coordinator._disconnect()

        client.close.assert_awaited_once()
        assert coordinator.client is None

    import asyncio

    asyncio.run(run_test())


def test_disconnect_closes_client_sync():
    """Ensure _disconnect handles sync client.close."""

    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator.from_params(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        client = MagicMock()
        coordinator.client = client

        await coordinator._disconnect()

        client.close.assert_called_once()
        assert coordinator.client is None

    import asyncio

    asyncio.run(run_test())


def test_scan_device_closes_client_on_failure():
    """Ensure scan_device closes the client even when scan fails."""

    async def run_test():
        scanner = await ThesslaGreenDeviceScanner.create("localhost", 502)
        scanner.scan = AsyncMock(side_effect=ConnectionException("fail"))
        scanner.close = AsyncMock()

        with pytest.raises(ConnectionException):
            await scanner.scan_device()

        scanner.close.assert_awaited_once()

    import asyncio

    asyncio.run(run_test())


def test_close_handles_io_error():
    """Scanner.close should swallow errors from client.close."""

    async def run_test():
        scanner = await ThesslaGreenDeviceScanner.create("localhost", 502)
        client = AsyncMock()
        client.close.side_effect = OSError("boom")
        scanner._client = client

        # Should not raise despite underlying error
        await scanner.close()

        client.close.assert_called_once()
        assert scanner._client is None

    import asyncio

    asyncio.run(run_test())


def test_close_closes_existing_client():
    """Scanner.close should await client.close and clear reference."""

    async def run_test():
        scanner = await ThesslaGreenDeviceScanner.create("localhost", 502)
        client = AsyncMock()

        async def close_side_effect():
            # _client should still point to client when close is called
            assert scanner._client is client
            return None

        client.close.side_effect = close_side_effect
        scanner._client = client

        await scanner.close()

        client.close.assert_awaited_once()
        assert scanner._client is None

    asyncio.run(run_test())
