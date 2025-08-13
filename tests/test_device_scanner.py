"""Test device scanner for ThesslaGreen Modbus integration."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.const import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    SENSOR_UNAVAILABLE,
)
from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusException
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS, INPUT_REGISTERS

pytestmark = pytest.mark.asyncio


async def test_device_scanner_initialization():
    """Test device scanner initialization."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)

    assert scanner.host == "192.168.3.17"
    assert scanner.port == 8899
    assert scanner.slave_id == 10


async def test_read_holding_skips_unresponsive_register(caplog):
    """Registers that fail repeatedly should be skipped on subsequent scans."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    caplog.set_level(logging.WARNING)
    with patch(
        "custom_components.thessla_green_modbus.device_scanner._call_modbus",
        AsyncMock(side_effect=ModbusException("boom")),
    ) as call_mock:
        result = await scanner._read_holding(mock_client, 0x00A8, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry

    # Second call should be skipped without calling modbus again
    with patch(
        "custom_components.thessla_green_modbus.device_scanner._call_modbus",
        AsyncMock(),
    ) as call_mock:
        result = await scanner._read_holding(mock_client, 0x00A8, 1)
        assert result is None
        call_mock.assert_not_called()

    assert 0x00A8 in scanner._failed_holding
    assert "0x00A8" in caplog.text


async def test_read_input_logs_warning_on_failure(caplog):
    """Warn when input registers cannot be read after retries."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    caplog.set_level(logging.WARNING)
    with patch(
        "custom_components.thessla_green_modbus.device_scanner._call_modbus",
        AsyncMock(side_effect=ModbusException("boom")),
    ) as call_mock:
        result = await scanner._read_input(mock_client, 0x0001, 3)
        assert result is None
        assert call_mock.await_count == scanner.retry

    assert (
        "Failed to read input registers 0x0001-0x0003 after 3 retries" in caplog.text
    )


async def test_scan_device_success_dynamic():
    """Test successful device scan with dynamic register scanning."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        data = [1] * count
        if address == 0:
            data[0:3] = [4, 85, 0]
        return data

    async def fake_read_holding(client, address, count):
        return [1] * count

    async def fake_read_coil(client, address, count):
        return [False] * count

    async def fake_read_discrete(client, address, count):
        return [False] * count

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            result = await scanner.scan_device()

    assert set(result["available_registers"]["input_registers"]) == set(INPUT_REGISTERS.keys())
    assert set(result["available_registers"]["holding_registers"]) == set(HOLDING_REGISTERS.keys())
    assert set(result["available_registers"]["coil_registers"]) == set(COIL_REGISTERS.keys())
    assert set(result["available_registers"]["discrete_inputs"]) == set(
        DISCRETE_INPUT_REGISTERS.keys()
    )
    assert result["device_info"]["firmware"] == "4.85.0"


@pytest.fixture
def mock_modbus_response():
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [4, 85, 0]
    response.bits = [False]
    return response


async def test_scan_device_success_static(mock_modbus_response):
    """Test successful device scan with predefined registers."""
    regs = {
        "04": {16: "outside_temperature"},
        "03": {0: "mode"},
        "01": {0: "power_supply_fans"},
        "02": {0: "expansion"},
    }
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client.read_input_registers.return_value = mock_modbus_response
            mock_client.read_holding_registers.return_value = mock_modbus_response
            mock_client.read_coils.return_value = mock_modbus_response
            mock_client.read_discrete_inputs.return_value = mock_modbus_response
            mock_client_class.return_value = mock_client

            result = await scanner.scan_device()

            assert "available_registers" in result
            assert "device_info" in result
            assert "capabilities" in result
            assert result["device_info"]["firmware"] == "4.85.0"
            assert "outside_temperature" in result["available_registers"]["input_registers"]
            assert "mode" in result["available_registers"]["holding_registers"]
            assert "power_supply_fans" in result["available_registers"]["coil_registers"]
            assert "expansion" in result["available_registers"]["discrete_inputs"]


async def test_scan_device_connection_failure():
    """Test device scan with connection failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Failed to connect"):
            await scanner.scan_device()
        await scanner.close()


async def test_scan_blocks_propagated():
    """Ensure scan_device returns discovered register blocks."""
    # Avoid scanning extra registers from CSV for test speed
    empty_regs = {"04": {}, "03": {}, "01": {}, "02": {}}
    with patch.object(
        ThesslaGreenDeviceScanner,
        "_load_registers",
        AsyncMock(return_value=(empty_regs, {})),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

        async def fake_read_input(client, address, count):
            return [1] * count

        async def fake_read_holding(client, address, count):
            return [1] * count

        async def fake_read_coil(client, address, count):
            return [False] * count

        async def fake_read_discrete(client, address, count):
            return [False] * count

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client_class.return_value = mock_client

            with (
                patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
                patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
                patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
                patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
            ):
                result = await scanner.scan_device()

    expected_blocks = {
        "input_registers": (
            min(INPUT_REGISTERS.values()),
            max(INPUT_REGISTERS.values()),
        ),
        "holding_registers": (
            min(HOLDING_REGISTERS.values()),
            max(HOLDING_REGISTERS.values()),
        ),
        "coil_registers": (
            min(COIL_REGISTERS.values()),
            max(COIL_REGISTERS.values()),
        ),
        "discrete_inputs": (
            min(DISCRETE_INPUT_REGISTERS.values()),
            max(DISCRETE_INPUT_REGISTERS.values()),
        ),
    }

    assert result["scan_blocks"] == expected_blocks


async def test_scan_device_batch_fallback():
    """Batch read failures should fall back to single-register reads."""
    empty_regs = {"04": {}, "03": {}, "01": {}, "02": {}}
    with (
        patch.object(
            ThesslaGreenDeviceScanner, "_load_registers", AsyncMock(return_value=(empty_regs, {}))
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"ir1": 0x10, "ir2": 0x11},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS",
            {"hr1": 0x20, "hr2": 0x21},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS",
            {"cr1": 0x00, "cr2": 0x01},
        ),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {"dr1": 0x00, "dr2": 0x01},
        ),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

        async def fake_read_input(client, address, count):
            if address == 0 and count == 5:
                return [4, 85, 0, 0, 0]
            if count > 1:
                return None
            return [0]

        async def fake_read_holding(client, address, count):
            if count > 1:
                return None
            return [0]

        async def fake_read_coil(client, address, count):
            if count > 1:
                return None
            return [False]

        async def fake_read_discrete(client, address, count):
            if count > 1:
                return None
            return [False]

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client_class.return_value = mock_client

            with (
                patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)) as ri,
                patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
                patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
                patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
            ):
                result = await scanner.scan_device()

    assert set(result["available_registers"]["input_registers"]) == {"ir1", "ir2"}
    assert set(result["available_registers"]["holding_registers"]) == {"hr1", "hr2"}
    assert set(result["available_registers"]["coil_registers"]) == {"cr1", "cr2"}
    assert set(result["available_registers"]["discrete_inputs"]) == {"dr1", "dr2"}

    # Ensure batch read was attempted and individual fallback reads occurred
    batch_calls = [call for call in ri.await_args_list if call.args[1] == 0x10]
    assert any(call.args[2] == 2 for call in batch_calls)
    assert any(call.args[2] == 1 for call in batch_calls)
async def test_temperature_register_unavailable_kept():
    """Temperature registers with SENSOR_UNAVAILABLE should remain available."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        data = [1] * count
        outside_addr = INPUT_REGISTERS["outside_temperature"]
        if address <= outside_addr < address + count:
            data[outside_addr - address] = SENSOR_UNAVAILABLE
        return data

    async def fake_read_holding(client, address, count):
        return [1] * count

    async def fake_read_coil(client, address, count):
        return [False] * count

    async def fake_read_discrete(client, address, count):
        return [False] * count

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            result = await scanner.scan_device()

    assert "outside_temperature" in result["available_registers"]["input_registers"]


async def test_is_valid_register_value():
    """Test register value validation."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    # Valid values
    assert scanner._is_valid_register_value("test_register", 100) is True
    assert scanner._is_valid_register_value("test_register", 0) is True

    # SENSOR_UNAVAILABLE should still be considered valid for temperature sensors
    assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True

    # Temperature sensor unavailable value should be considered valid
    assert (
        scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE)
        is True
    )


    # Invalid air flow value
    assert scanner._is_valid_register_value("supply_air_flow", 65535) is False

    # Mode values respect allowed set
    assert scanner._is_valid_register_value("mode", 1) is True
    assert scanner._is_valid_register_value("mode", 3) is False

    # Range from CSV
    assert scanner._is_valid_register_value("supply_percentage", 100) is True
    assert scanner._is_valid_register_value("supply_percentage", 200) is False

    # Dynamic percentage limits should accept device-provided values
    assert scanner._is_valid_register_value("min_percentage", 20) is True
    assert scanner._is_valid_register_value("max_percentage", 120) is True
    assert scanner._is_valid_register_value("min_percentage", -1) is False
    assert scanner._is_valid_register_value("max_percentage", 200) is False
    # BCD time registers
    scanner._register_ranges["schedule_start_time"] = (0, 2359)
    assert scanner._is_valid_register_value("schedule_start_time", 0x1234) is True
    assert scanner._is_valid_register_value("schedule_start_time", 0x2460) is False


async def test_scan_includes_unavailable_temperature():
    """Temperature register with SENSOR_UNAVAILABLE should remain available."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)

    async def fake_read_input(client, address, count):
        data = [1] * count
        if address == 0:
            data[0:3] = [4, 85, 0]
        temp_addr = INPUT_REGISTERS["outside_temperature"]
        if address <= temp_addr < address + count:
            data[temp_addr - address] = SENSOR_UNAVAILABLE
        return data

    async def fake_read_holding(client, address, count):
        return [1] * count

    async def fake_read_coil(client, address, count):
        return [False] * count

    async def fake_read_discrete(client, address, count):
        return [False] * count

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with (
            patch.object(scanner, "_read_input", AsyncMock(side_effect=fake_read_input)),
            patch.object(scanner, "_read_holding", AsyncMock(side_effect=fake_read_holding)),
            patch.object(scanner, "_read_coil", AsyncMock(side_effect=fake_read_coil)),
            patch.object(scanner, "_read_discrete", AsyncMock(side_effect=fake_read_discrete)),
        ):
            result = await scanner.scan_device()

    assert "outside_temperature" in result["available_registers"]["input_registers"]


async def test_capabilities_detect_schedule_keywords():
    """Ensure capability detection considers scheduling related registers."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner.available_registers["holding_registers"].add("airing_start_time")
    caps = scanner._analyze_capabilities()
    assert caps.weekly_schedule is True


async def test_load_registers_duplicate_warning(tmp_path, caplog):
    """Warn when duplicate register addresses are encountered."""
    csv_content = "Function_Code,Register_Name,Address_DEC\n" "04,reg_a,1\n" "04,reg_b,1\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch("custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
    ):
        with caplog.at_level(logging.WARNING):
            await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert any("Duplicate register address" in record.message for record in caplog.records)


async def test_load_registers_duplicate_names(tmp_path):
    """Ensure duplicate register names are suffixed for uniqueness."""
    csv_content = "Function_Code,Register_Name,Address_DEC\n" "04,reg_a,1\n" "04,reg_a,2\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch("custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
    ):
        scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert scanner._registers["04"] == {1: "reg_a_1", 2: "reg_a_2"}


async def test_load_registers_missing_range_warning(tmp_path, caplog):
    """Warn when Min/Max range is incomplete."""
    csv_content = "Function_Code,Address_DEC,Register_Name,Min,Max\n" "04,1,reg_a,0,\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_a": 1},
        ),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        caplog.at_level(logging.WARNING),
    ):
        await ThesslaGreenDeviceScanner.create("host", 502, 10)

    assert any("Incomplete range" in record.message for record in caplog.records)


async def test_load_registers_missing_required_register(tmp_path):
    """Fail fast when a required register is absent from CSV."""
    csv_content = "Function_Code,Address_DEC,Register_Name\n"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "modbus_registers.csv").write_text(csv_content)

    with (
        patch("custom_components.thessla_green_modbus.device_scanner.files", return_value=tmp_path),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.INPUT_REGISTERS",
            {"reg_a": 1},
        ),
        patch("custom_components.thessla_green_modbus.device_scanner.HOLDING_REGISTERS", {}),
        patch("custom_components.thessla_green_modbus.device_scanner.COIL_REGISTERS", {}),
        patch(
            "custom_components.thessla_green_modbus.device_scanner.DISCRETE_INPUT_REGISTERS",
            {},
        ),
    ):
        with pytest.raises(ValueError, match="reg_a"):
            await ThesslaGreenDeviceScanner.create("host", 502, 10)


async def test_analyze_capabilities():
    """Test capability analysis."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    # Mock available registers
    scanner.available_registers = {
        "input_registers": {"constant_flow_active", "outside_temperature"},
        "holding_registers": {"gwc_mode", "bypass_mode"},
        "coil_registers": {"power_supply_fans"},
        "discrete_inputs": {"expansion"},
    }

    capabilities = scanner._analyze_capabilities()

    assert capabilities.constant_flow is True
    assert capabilities.gwc_system is True
    assert capabilities.bypass_system is True
    assert capabilities.expansion_module is True
    assert capabilities.sensor_outside_temperature is True


async def test_analyze_capabilities_flag_presence():
    """Capabilities should reflect register presence and absence."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    # Positive case: registers exist
    scanner.available_registers = {
        "input_registers": {"constant_flow_active", "outside_temperature"},
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    capabilities = scanner._analyze_capabilities()

    assert capabilities.constant_flow is True
    assert capabilities.sensor_outside_temperature is True

    # Negative case: registers absent
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    capabilities = scanner._analyze_capabilities()

    assert capabilities.constant_flow is False
    assert capabilities.sensor_outside_temperature is False


@pytest.mark.parametrize("async_close", [True, False])
async def test_close_terminates_client(async_close):
    """Ensure close() handles both async and sync client close methods."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    mock_client = AsyncMock() if async_close else MagicMock()
    scanner._client = mock_client

    await scanner.close()

    if async_close:
        mock_client.close.assert_called_once()
        mock_client.close.assert_awaited_once()
    else:
        mock_client.close.assert_called_once()

    assert scanner._client is None
