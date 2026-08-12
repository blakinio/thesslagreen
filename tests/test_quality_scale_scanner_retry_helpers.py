# mypy: ignore-errors
"""Risk-focused coverage for scanner capability, firmware, grouping, and retry helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.core import register_groups
from custom_components.thessla_green_modbus.core import retry as core_retry
from custom_components.thessla_green_modbus.scanner import capabilities, firmware
from custom_components.thessla_green_modbus.scanner.device_info import (
    DeviceCapabilities,
    ScannerDeviceInfo,
)
from custom_components.thessla_green_modbus.transport import retry as transport_retry
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException


def test_transport_retry_decision_equality_hash_and_jitter_paths() -> None:
    decision = transport_retry.RetryDecision(
        retry=True,
        kind=transport_retry.ErrorKind.TRANSIENT,
        reason="timeout",
    )
    assert decision == transport_retry.RetryDecision(
        retry=True,
        kind=transport_retry.ErrorKind.TRANSIENT,
        reason="timeout",
    )
    assert decision == ("transient", "timeout")
    assert (decision == ("transient",)) is False
    assert (decision == object()) is False
    assert isinstance(hash(decision), int)

    assert transport_retry.should_retry(decision, 1, 2) is True
    assert transport_retry.should_retry(decision, 2, 2) is False
    assert transport_retry.should_retry(transport_retry.ErrorKind.PERMANENT, 1, 2) is False

    with patch.object(transport_retry.random, "uniform", return_value=0.25) as uniform:
        assert (
            transport_retry.calculate_backoff(
                attempt=2,
                base=1.0,
                jitter=(0.1, 0.5),
            )
            == 2.25
        )
    uniform.assert_called_once_with(0.1, 0.5)

    with patch.object(transport_retry.random, "uniform", return_value=-5.0):
        assert (
            transport_retry.calculate_backoff(
                attempt=1,
                base=1.0,
                jitter=5.0,
            )
            == 0.0
        )
    assert (
        transport_retry.calculate_backoff(
            attempt=4,
            base=1.0,
            max_backoff=3.0,
        )
        == 3.0
    )


def test_transport_error_classification_remaining_modbus_shapes() -> None:
    cancelled_io = transport_retry.classify_transport_error(ModbusIOException("request cancelled"))
    assert cancelled_io.reason == "cancelled"
    assert cancelled_io.kind is transport_retry.ErrorKind.TRANSIENT

    permanent = transport_retry.classify_transport_error(ModbusException("other"))
    assert permanent.kind is transport_retry.ErrorKind.PERMANENT
    assert permanent.reason == "modbus"
    assert transport_retry._is_unsupported_register_error(ValueError("ordinary")) is False


def _cap_scanner(**overrides):
    data = {
        "capabilities": DeviceCapabilities(),
        "available_registers": {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
        "_register_ranges": {},
        "_unsupported_input_ranges": {},
        "_unsupported_holding_ranges": {},
        "_failed_input": set(),
        "_failed_holding": set(),
        "_reported_invalid": set(),
        "verbose_invalid_values": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_register_value_validation_range_and_bcd_edges() -> None:
    scanner = _cap_scanner(_register_ranges={"bounded": (1, 3)})
    assert capabilities.is_valid_register_value(scanner, "bounded", 0) is False
    assert capabilities.is_valid_register_value(scanner, "bounded", 4) is False
    assert capabilities.is_valid_register_value(scanner, "bounded", 2) is True
    assert capabilities.is_valid_register_value(scanner, "bounded", 65535) is False

    with patch.object(capabilities, "decode_bcd_time", return_value=None):
        assert capabilities.is_valid_register_value(scanner, "schedule_monday", 1234) is False
    with patch.object(capabilities, "decode_bcd_time", return_value=(12, 34)):
        assert capabilities.is_valid_register_value(scanner, "schedule_monday", 1234) is True


def test_capability_analysis_and_range_cache_mutations() -> None:
    scanner = _cap_scanner()
    scanner.available_registers = {
        "input_registers": {
            "outside_temperature",
            "gwc_temperature",
            "constant_flow_active",
        },
        "holding_registers": {"schedule_monday_1", "on_off_panel_mode"},
        "coil_registers": {"gwc", "bypass"},
        "discrete_inputs": {"expansion"},
    }
    caps = capabilities.analyze_capabilities(scanner)
    assert caps.sensor_outside_temperature is True
    assert caps.expansion_module is True
    assert caps.gwc_system is True
    assert caps.bypass_system is True
    assert caps.weekly_schedule is True
    assert caps.basic_control is True
    assert caps.constant_flow is True

    scanner._unsupported_input_ranges = {(10, 20): 2}
    scanner._unsupported_holding_ranges = {(30, 40): 2}
    assert capabilities.filter_unsupported_addresses(
        scanner, "input_registers", {9, 10, 15, 21}
    ) == {9, 21}
    assert capabilities.filter_unsupported_addresses(
        scanner, "holding_registers", {29, 30, 35, 41}
    ) == {29, 41}
    assert capabilities.filter_unsupported_addresses(scanner, "coils", {1, 2}) == {1, 2}

    scanner._failed_input = {15}
    scanner._unsupported_input_ranges = {(10, 20): 2}
    capabilities.mark_input_supported(scanner, 15)
    assert scanner._unsupported_input_ranges == {(10, 14): 2, (16, 20): 2}
    assert 15 not in scanner._failed_input

    scanner._failed_holding = {35}
    scanner._unsupported_holding_ranges = {(30, 40): 3}
    capabilities.mark_holding_supported(scanner, 35)
    assert scanner._unsupported_holding_ranges == {(30, 34): 3, (36, 40): 3}

    scanner._unsupported_holding_ranges = {(10, 20): 1}
    capabilities.mark_holding_unsupported(scanner, 14, 16, 2)
    assert scanner._unsupported_holding_ranges == {
        (10, 13): 1,
        (17, 20): 1,
        (14, 16): 2,
    }

    scanner._unsupported_input_ranges = {(10, 15): 1, (20, 25): 2}
    capabilities.mark_input_unsupported(scanner, 14, 22, None)
    assert scanner._unsupported_input_ranges == {(10, 25): 0}


def test_invalid_value_logging_repeated_and_verbose_paths() -> None:
    scanner = _cap_scanner()
    with (
        patch.object(capabilities, "_format_register_value", return_value="decoded"),
        patch.object(capabilities._LOGGER, "log") as log,
    ):
        capabilities.log_invalid_value(scanner, "bad", 99)
        capabilities.log_invalid_value(scanner, "bad", 99)
        assert log.call_count == 1
        scanner.verbose_invalid_values = True
        capabilities.log_invalid_value(scanner, "bad", 99)
        assert log.call_count == 2


class _BadInfoRegs:
    def __len__(self):
        return 10000

    def __getitem__(self, index):
        raise RuntimeError("bad firmware value")


def test_firmware_parse_unexpected_value_errors_are_recorded() -> None:
    with patch.dict(
        firmware.INPUT_REGISTERS,
        {"version_major": 0, "version_minor": 1, "version_patch": 2},
        clear=False,
    ):
        major, minor, patch_version, error = firmware._parse_version_from_info_regs(_BadInfoRegs())
    assert (major, minor, patch_version) == (None, None, None)
    assert isinstance(error, RuntimeError)


@pytest.mark.asyncio
async def test_firmware_probe_missing_parts_signature_fallback_and_errors() -> None:
    scanner = SimpleNamespace(_client=object(), _read_input=AsyncMock(side_effect=TypeError()))
    scanner._read_input.side_effect = [TypeError(), [4], TypeError(), [85], TypeError(), [7]]
    with patch.dict(
        firmware.INPUT_REGISTERS,
        {"version_major": 0, "version_minor": 1, "version_patch": 2},
        clear=False,
    ):
        result = await firmware._probe_missing_version_parts(scanner, None, None, None, None)
    assert result[:3] == (4, 85, 7)

    scanner = SimpleNamespace(_client=None, _read_input=AsyncMock(side_effect=ValueError("bad")))
    with patch.dict(
        firmware.INPUT_REGISTERS,
        {"version_major": 0, "version_minor": 1, "version_patch": 2},
        clear=False,
    ):
        result = await firmware._probe_missing_version_parts(scanner, None, None, None, None)
    assert isinstance(result[3], ValueError)

    scanner = SimpleNamespace(_client=None, _read_input=AsyncMock(side_effect=RuntimeError("bad")))
    with patch.dict(
        firmware.INPUT_REGISTERS,
        {"version_major": 0, "version_minor": 1, "version_patch": 2},
        clear=False,
    ):
        result = await firmware._probe_missing_version_parts(scanner, None, None, None, None)
    assert isinstance(result[3], RuntimeError)


@pytest.mark.asyncio
async def test_firmware_partial_identity_and_device_identity_error_paths() -> None:
    device = ScannerDeviceInfo()
    firmware._apply_firmware_version_to_device(device, 4, 85, None, ValueError("patch"))
    assert device.firmware == "4.85"
    assert device.firmware_available is True

    device = ScannerDeviceInfo()
    firmware._apply_firmware_version_to_device(device, None, None, None, ValueError("bad"))
    assert device.firmware_available is False

    scanner = SimpleNamespace(_read_holding_block=AsyncMock(return_value=[0x4142, 0x4300]))
    device = ScannerDeviceInfo()
    with (
        patch.dict(firmware.INPUT_REGISTERS, {"serial_number": 0}, clear=False),
        patch.dict(firmware.HOLDING_REGISTERS, {"device_name": 0}, clear=False),
        patch.dict(
            firmware.REGISTER_DEFINITIONS,
            {
                "serial_number": SimpleNamespace(length=2),
                "device_name": SimpleNamespace(length=2),
            },
            clear=False,
        ),
    ):
        await firmware.scan_device_identity(scanner, [0x0001, 0x0002], device)
    assert device.serial_number == "00010002"
    assert device.device_name == "ABC"

    scanner = SimpleNamespace(_read_holding_block=AsyncMock(side_effect=RuntimeError("name")))
    with patch.dict(firmware.INPUT_REGISTERS, {}, clear=True):
        await firmware.scan_device_identity(scanner, _BadInfoRegs(), ScannerDeviceInfo())


def _group_client(*, safe_scan: bool):
    return SimpleNamespace(
        _register_groups={"old": [(1, 1)]},
        available_registers={"holding_registers": {"good", "bad", "missing"}},
        _register_maps={"holding_registers": {"good": 10, "bad": 20}},
        safe_scan=safe_scan,
        effective_batch=4,
    )


def test_register_groups_unexpected_definition_errors_in_both_modes() -> None:
    def definition(name):
        if name == "bad":
            raise ValueError("bad definition")
        return SimpleNamespace(length=2)

    safe = _group_client(safe_scan=True)
    register_groups.compute_register_groups(
        safe,
        get_register_definition=definition,
        group_reads=Mock(),
        holding_batch_boundaries=frozenset(),
    )
    assert set(safe._register_groups["holding_registers"]) == {(10, 2), (20, 1)}

    grouped = _group_client(safe_scan=False)
    group_reads = Mock(return_value=[(10, 2), (20, 1)])
    register_groups.compute_register_groups(
        grouped,
        get_register_definition=definition,
        group_reads=group_reads,
        holding_batch_boundaries=frozenset({20}),
    )
    group_reads.assert_called_once()
    assert group_reads.call_args.kwargs["boundaries"] == frozenset({20})


@pytest.mark.asyncio
async def test_core_retry_disconnect_and_exception_paths() -> None:
    owner = SimpleNamespace(
        device_client=SimpleNamespace(client=object(), retry=3, _transport=None),
        _disconnect=AsyncMock(),
        _ensure_connection=AsyncMock(),
        backoff=0.1,
        _log_read_retry=Mock(),
    )
    previous = owner.device_client.client
    owner._disconnect.side_effect = lambda: setattr(owner.device_client, "client", None)
    assert (
        await core_retry._safe_disconnect_for_retry(
            owner,
            register_type="holding",
            start_address=10,
            attempt=1,
            restore_client=True,
        )
        is None
    )
    assert owner.device_client.client is previous

    owner._disconnect = AsyncMock(side_effect=TimeoutError("disconnect"))
    error = await core_retry._safe_disconnect_for_retry(
        owner,
        register_type="holding",
        start_address=10,
        attempt=1,
        restore_client=False,
    )
    assert isinstance(error, TimeoutError)

    owner._disconnect = AsyncMock()
    owner.device_client._transport = object()
    owner._ensure_connection = AsyncMock(side_effect=ConnectionException("reconnect"))
    error = await core_retry.disconnect_and_reconnect_for_retry(
        owner,
        register_type="holding",
        start_address=10,
        attempt=1,
    )
    assert isinstance(error, ConnectionException)

    owner._ensure_connection = AsyncMock()
    owner._disconnect = AsyncMock()
    owner._log_read_retry = Mock()
    exc = ConnectionException("read")
    returned = await core_retry._handle_retry_exception(
        owner,
        register_type="holding",
        start_address=10,
        attempt=1,
        exc=exc,
        reconnect=False,
    )
    assert returned is exc
    owner._log_read_retry.assert_called_once()

    with pytest.raises(ConnectionException):
        await core_retry._handle_retry_exception(
            owner,
            register_type="holding",
            start_address=10,
            attempt=3,
            exc=exc,
            reconnect=False,
        )


def test_core_retry_classification_and_logging_delegate() -> None:
    assert core_retry.classify_retry_error(TimeoutError()) == ("transient", "timeout")
    with patch.object(core_retry, "log_retry_attempt") as log:
        core_retry.log_coordinator_retry(
            operation="read",
            attempt=1,
            max_attempts=3,
            exc=TimeoutError(),
            backoff=0.1,
        )
    log.assert_called_once()
