from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import custom_components.thessla_green_modbus.scanner.core as sc
import pytest
from custom_components.thessla_green_modbus.registers.loader import clear_cache, get_registers_path


def test_scanner_register_cache_invalidation(tmp_path: Path, monkeypatch) -> None:
    """Scanner should rebuild register maps when definitions change."""
    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(get_registers_path().read_text(), encoding="utf-8")
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        tmp_json,
    )

    clear_cache()
    sc.REGISTER_DEFINITIONS.clear()
    sc.INPUT_REGISTERS.clear()
    sc.HOLDING_REGISTERS.clear()
    sc.COIL_REGISTERS.clear()
    sc.DISCRETE_INPUT_REGISTERS.clear()
    sc.MULTI_REGISTER_SIZES.clear()
    sc.REGISTER_HASH = None


@pytest.mark.asyncio
async def test_full_register_scan_batches_reads() -> None:
    """Full register scans should batch contiguous addresses."""
    reg_map = {4: {0: "ir0", 2: "ir2"}, 3: {0: "hr0", 2: "hr2"}, 1: {}, 2: {}}
    with patch.object(
        sc.ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(reg_map, {})),
    ):
        scanner = await sc.ThesslaGreenDeviceScanner.create(
            "192.168.1.1", 502, 10, full_register_scan=True
        )

    input_calls: list[tuple[int, int]] = []
    holding_calls: list[tuple[int, int]] = []

    async def fake_read_input(client, address, count, **kwargs):
        input_calls.append((address, count))
        return [0] * count

    async def fake_read_holding(client, address, count, **kwargs):
        holding_calls.append((address, count))
        return [0] * count

    with (
        patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class,
        patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
        patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=[False])),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=[False])),
        patch.object(scanner, "_is_valid_register_value", return_value=True),
    ):
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()
        mock_client_class.return_value = mock_client
        await scanner.scan_device()

    assert (0, 3) in input_calls
    assert (0, 3) in holding_calls
