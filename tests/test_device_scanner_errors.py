from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


@pytest.mark.asyncio
async def test_scan_device_scan_returns_non_dict_raises():
    scanner = await _make_scanner()

    async def fake_scan(self_arg):
        return "not_a_dict"

    with patch.object(ThesslaGreenDeviceScanner, "scan", fake_scan):
        with patch.object(scanner, "close", AsyncMock()):
            with pytest.raises(TypeError, match="scan\\(\\) must return a dict"):
                await scanner.scan_device()


@pytest.mark.asyncio
async def test_scan_device_main_scan_non_dict_raises():
    scanner = await _make_scanner()

    async def fake_scan_non_dict(self_arg):
        return "not_a_dict"

    mock_transport = AsyncMock()
    mock_transport.client = AsyncMock()

    with patch.object(ThesslaGreenDeviceScanner, "scan", fake_scan_non_dict):
        with patch.object(scanner, "_build_tcp_transport", return_value=mock_transport):
            with patch.object(scanner, "close", AsyncMock()):
                with pytest.raises(TypeError, match="scan\\(\\) must return a dict"):
                    await scanner.scan_device()


@pytest.mark.asyncio
async def test_scan_device_legacy_returns_dict():
    scanner = await _make_scanner()

    async def fake_scan_returns_dict():
        return {"custom_key": "custom_value"}

    scanner.scan = fake_scan_returns_dict  # type: ignore[method-assign]

    with patch.object(scanner, "close", AsyncMock()):
        result = await scanner.scan_device()

    assert result == {"custom_key": "custom_value"}


@pytest.mark.asyncio
async def test_scan_device_importlib_fails():
    scanner = await _make_scanner()
    mock_transport = AsyncMock()
    mock_transport.client = AsyncMock()

    with (
        patch.object(scanner, "_build_tcp_transport", return_value=mock_transport),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    assert "available_registers" in result
