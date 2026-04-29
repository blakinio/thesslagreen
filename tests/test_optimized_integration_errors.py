"""Error and offline behavior tests for optimized integration."""

from unittest.mock import AsyncMock, patch

import pytest


class TestThesslaGreenDeviceScannerErrors:
    @pytest.mark.asyncio
    async def test_scanner_core_connection_failure(self):
        from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
        from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

        mock_transport = AsyncMock()
        mock_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("connection refused"))
        mock_transport.close = AsyncMock()

        with (
            patch.object(scanner, "_build_auto_tcp_attempts", return_value=[("tcp", mock_transport, 5.0)]),
            pytest.raises(ConnectionException, match=r"(connect|transport failed)"),
        ):
            await scanner.scan_device()
