"""Guards reproduced by physical acceptance on AirPack Home firmware 3.11."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus.capability_rules import firmware_block_reason
from custom_components.thessla_green_modbus.number import ThesslaGreenNumber
from custom_components.thessla_green_modbus.registers.loader import get_all_registers
from custom_components.thessla_green_modbus.services import handlers_maintenance as maintenance
from homeassistant.exceptions import ServiceValidationError

from tests.helpers_coordinator import make_coordinator


@pytest.mark.parametrize(
    "name,firmware,blocked",
    [
        ("airing_switch_coef", "3.11", True),
        ("airing_switch_coef", "3.99", True),
        ("airing_switch_coef", "4.84", True),
        ("airing_switch_coef", "4.85", False),
        ("open_window_coef", "3.11", True),
        ("open_window_coef", "3.71", True),
        ("open_window_coef", "3.72", False),
        ("open_window_coef", "4.71", True),
        ("open_window_coef", "4.72", False),
        ("open_window_coef", " v4.72.0 ", False),
        ("open_window_coef", "Unknown", False),
        ("open_window_coef", "4", False),
        ("open_window_coef", None, False),
        ("airing_coef", "3.11", False),
        ("open_window_coef", "5.0", False),
    ],
)
def test_documented_firmware_boundaries(name, firmware, blocked):
    assert bool(firmware_block_reason(name, firmware)) is blocked


@pytest.mark.parametrize("name", ["airing_switch_coef", "open_window_coef"])
async def test_311_reserved_words_cannot_send_writes(name):
    device = make_coordinator()
    device.device_client.device_info["firmware"] = "3.11"
    device._ensure_connection = AsyncMock()
    assert await device.async_write_register(name, 100, refresh=False) is False
    device._ensure_connection.assert_not_awaited()


@pytest.mark.parametrize("name", ["airing_switch_coef", "open_window_coef"])
def test_existing_311_number_is_unavailable(mock_coordinator, name):
    mock_coordinator.device_client.device_info["firmware"] = "3.11"
    entity = ThesslaGreenNumber(
        mock_coordinator, name, {"min": 10, "max": 100, "step": 1}, "holding_registers"
    )
    assert entity.available is False


@pytest.mark.parametrize(
    "definition",
    [r for r in get_all_registers() if "W" not in r.access],
    ids=lambda r: f"{r.function}_{r.address}_{r.name}",
)
async def test_every_readonly_definition_rejects_write_before_connection(definition):
    device = make_coordinator()
    device._ensure_connection = AsyncMock()
    assert await device.async_write_register(definition.name, 0, refresh=False) is False
    device._ensure_connection.assert_not_awaited()


async def test_uart_preflight_rejects_before_partial_update():
    device = SimpleNamespace(
        device_client=SimpleNamespace(available_registers={"holding_registers": {"uart_0_baud"}})
    )
    deps = SimpleNamespace(
        normalize_option=lambda x: x,
        iter_target_coordinators=AsyncMock(return_value=[("climate.unit", device)]),
        write_register=AsyncMock(),
    )
    handler = maintenance._build_set_modbus_parameters_handler(object(), deps)
    with pytest.raises(ServiceValidationError, match="uart_0_parity"):
        await handler(
            SimpleNamespace(data={"port": "air_b", "baud_rate": "9600", "parity": "none"})
        )
    deps.write_register.assert_not_awaited()


@pytest.mark.parametrize("firmware,exposed", [("3.11", False), ("4.85", True)])
async def test_number_setup_excludes_reserved_firmware_controls(
    mock_coordinator, firmware, exposed
):
    from custom_components.thessla_green_modbus.number import async_setup_entry

    names = {"airing_switch_coef", "open_window_coef"}
    mock_coordinator.device_client.device_info["firmware"] = firmware
    mock_coordinator.device_client.available_registers["holding_registers"].update(names)
    added = []
    await async_setup_entry(
        None,
        SimpleNamespace(runtime_data=mock_coordinator),
        lambda entities, *args: added.extend(entities),
    )
    created = {e.register_name for e in added}
    assert bool(created & names) is exposed


@pytest.mark.parametrize("batch", [1, 2, 16])
async def test_diagnostic_reads_keep_vendor_atomic_blocks(batch, monkeypatch):
    from custom_components.thessla_green_modbus.services import handlers_data

    device = make_coordinator()
    device._ensure_connection = AsyncMock()
    device.device_client._register_maps = {
        "holding_registers": {
            "date_time": 0,
            "date_time_ddtt": 1,
            "date_time_ggmm": 2,
            "date_time_sscc": 3,
            "lock_date": 7,
            "lock_date_00mm": 8,
            "lock_date_00dd": 9,
            "mode": 4208,
        }
    }
    calls = []

    async def read(client, kind, address, count):
        calls.append((address, count))
        assert not (0 <= address <= 3 and (address, count) != (0, 4))
        assert not (7 <= address <= 9 and (address, count) != (7, 3))
        return SimpleNamespace(registers=[0] * count, isError=lambda: False)

    monkeypatch.setattr(handlers_data, "_read_batch_via_existing_client", read)
    available, missing, unknown, _, _ = await handlers_data._read_known_registers_safe(
        device, batch, 0
    )
    assert len(available["holding_registers"]) == 8
    assert not missing["holding_registers"] and not unknown["holding_registers"]
    assert calls[:2] == [(0, 4), (7, 3)]


@pytest.mark.parametrize("raises", [False, True])
async def test_failed_atomic_block_is_not_retried_as_invalid_single_words(monkeypatch, raises):
    from custom_components.thessla_green_modbus.services import handlers_data

    device = make_coordinator()
    device._ensure_connection = AsyncMock()
    device.device_client._register_maps = {
        "holding_registers": {"date_time": 0, "date_time_ddtt": 1}
    }
    calls = []

    async def read(client, kind, address, count):
        calls.append((address, count))
        if raises:
            raise TimeoutError()
        return SimpleNamespace(registers=[], isError=lambda: True)

    monkeypatch.setattr(handlers_data, "_read_batch_via_existing_client", read)
    available, missing, unknown, _, _ = await handlers_data._read_known_registers_safe(device, 1, 0)
    assert calls == [(0, 4)]
    assert not available["holding_registers"]
    assert len(unknown["holding_registers"] if raises else missing["holding_registers"]) == 2


@pytest.mark.parametrize(
    "words,expected",
    [
        ([0x1A, 0x2B, 0x3C, 0x4D, 0x5E, 0x6F], "1A2B3C4D5E6F"),
        ([0x12, 0x34, 0x56, 0x78, 0, 0], "123456780000"),
        ([0, 1, 2, 3, 4, 0], "000102030400"),
    ],
)
def test_serial_is_six_hex_bytes_preserving_leading_and_trailing_zeros(words, expected):
    from custom_components.thessla_green_modbus.registers.loader import get_register_definition

    assert get_register_definition("serial_number").decode(words) == expected


@pytest.mark.parametrize("words", [[], [1, 2], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 256]])
def test_serial_rejects_partial_or_nonbyte_values(words):
    from custom_components.thessla_green_modbus.registers.loader import get_register_definition

    with pytest.raises(ValueError, match="all six"):
        get_register_definition("serial_number").decode(words)


def test_corrected_serial_prefix_migrates_existing_entity_identity():
    from tests.test_migrate_unique_id import migrate_unique_id

    old = "001200340056007800000000_10_supply_percentage_272"
    assert (
        migrate_unique_id(old, serial_number="123456780000", host="test", port=8899, slave_id=10)
        == "123456780000_10_supply_percentage_272"
    )


@pytest.mark.parametrize("serial", [None, "short", "xxxxxxxxxxxx"])
def test_invalid_serial_does_not_change_device_registry(serial):
    from custom_components.thessla_green_modbus._setup import _migrate_serial_device_identifier

    _migrate_serial_device_identifier(object(), SimpleNamespace(entry_id="unit"), serial)


@pytest.mark.parametrize("previous", ["serial:001200340056007800000000", "entry:unit"])
def test_corrected_serial_keeps_existing_device_id(monkeypatch, previous):
    from unittest.mock import Mock

    from custom_components.thessla_green_modbus._setup import _migrate_serial_device_identifier
    from custom_components.thessla_green_modbus.const import DOMAIN
    from homeassistant.helpers import device_registry as dr

    registry = Mock()
    old = (DOMAIN, previous)
    device = SimpleNamespace(id="existing-device", identifiers={old})
    other = SimpleNamespace(id="unrelated", identifiers={(DOMAIN, "serial:other")})
    monkeypatch.setattr(dr, "async_get", lambda _: registry)
    monkeypatch.setattr(dr, "async_entries_for_config_entry", lambda *_: [device, other])
    _migrate_serial_device_identifier(object(), SimpleNamespace(entry_id="unit"), "123456780000")
    registry.async_update_device.assert_called_once_with(
        "existing-device",
        new_identifiers={old, (DOMAIN, "serial:123456780000")},
        serial_number="123456780000",
    )


def test_serial_device_migration_handles_unavailable_registry(monkeypatch):
    from custom_components.thessla_green_modbus._setup import _migrate_serial_device_identifier
    from homeassistant.helpers import device_registry as dr

    def unavailable(_):
        raise KeyError("registry")

    monkeypatch.setattr(dr, "async_get", unavailable)
    _migrate_serial_device_identifier(object(), SimpleNamespace(entry_id="unit"), "123456780000")


def test_invalid_full_serial_is_dropped_without_losing_other_poll_values():
    from custom_components.thessla_green_modbus.core.register_processing import (
        assemble_multi_register_values,
    )

    data = {"serial_number": "stale", "outside_temperature": 10.5}
    assemble_multi_register_values(4, {"serial_number"}, {24 + i: 0x4142 for i in range(6)}, data)
    assert data == {"outside_temperature": 10.5}


async def test_identity_reads_serial_block_when_optional_info_words_are_absent(monkeypatch):
    from custom_components.thessla_green_modbus.registers.loader import get_register_definition
    from custom_components.thessla_green_modbus.scanner import firmware
    from custom_components.thessla_green_modbus.scanner.device_info import ScannerDeviceInfo
    from custom_components.thessla_green_modbus.scanner.firmware import scan_device_identity

    monkeypatch.setitem(firmware.INPUT_REGISTERS, "serial_number", 24)
    monkeypatch.setitem(firmware.HOLDING_REGISTERS, "device_name", 8144)
    for name in ("serial_number", "device_name"):
        monkeypatch.setitem(firmware.REGISTER_DEFINITIONS, name, get_register_definition(name))
    scanner = SimpleNamespace(
        _read_input_block=AsyncMock(return_value=[0x12, 0x34, 0x56, 0x78, 0, 0]),
        _read_holding_block=AsyncMock(return_value=[0] * 8),
    )
    device = ScannerDeviceInfo()
    await scan_device_identity(scanner, [], device)
    assert device.serial_number == "123456780000"
    scanner._read_input_block.assert_awaited_once_with(24, 6)


@pytest.mark.parametrize("current", [[70], [80]])
async def test_311_mode_two_preserves_target_and_activates_atomic_triplet(current):
    from unittest.mock import Mock

    device = make_coordinator()
    device.device_client.device_info["firmware"] = "3.11"
    device._ensure_connection = AsyncMock()
    device._assert_write_connection_ready = Mock()
    device._locked_read_holding_registers = AsyncMock(side_effect=[current, [2]])
    device._write_holding_multi = AsyncMock(return_value=(None, True))
    device._handle_successful_single_register_write = Mock(return_value=False)
    assert await device._locked_single_register_write(
        register_name="mode", value=2, offset=0, refresh=False
    ) == (True, False)
    device._write_holding_multi.assert_awaited_once_with(4400, [2, current[0], 1], 1)


@pytest.mark.parametrize("current", [None, [], [0], [101]])
async def test_311_mode_two_cannot_invent_an_unknown_temporary_target(current):
    from unittest.mock import Mock

    device = make_coordinator()
    device.device_client.device_info["firmware"] = "3.11"
    device._ensure_connection = AsyncMock()
    device._assert_write_connection_ready = Mock()
    device._locked_read_holding_registers = AsyncMock(return_value=current)
    device._write_holding_multi = AsyncMock()
    assert await device._locked_single_register_write(
        register_name="mode", value=2, offset=0, refresh=False
    ) == (False, False)
    device._write_holding_multi.assert_not_awaited()


@pytest.mark.parametrize("write_ok,readback", [(False, [2]), (True, [1])])
async def test_311_mode_two_requires_effective_mode_readback(write_ok, readback):
    from unittest.mock import Mock

    device = make_coordinator()
    device.device_client.device_info["firmware"] = "3.11"
    device._ensure_connection = AsyncMock()
    device._assert_write_connection_ready = Mock()
    device._locked_read_holding_registers = AsyncMock(side_effect=[[80], readback])
    device._write_holding_multi = AsyncMock(return_value=(None, write_ok))
    assert await device._locked_single_register_write(
        register_name="mode", value=2, offset=0, refresh=False
    ) == (False, False)
