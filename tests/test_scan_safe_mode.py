# mypy: ignore-errors
"""Tests for scan_all_registers safe/slow mode and validate_known_registers service."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Test helpers (mirrors test_services_handlers_targets.py pattern)
# ---------------------------------------------------------------------------


class _Services:
    def __init__(self):
        self.handlers: dict = {}
        self.removed: list = []

    def async_register(self, _domain, service, handler, _schema):
        self.handlers[service] = handler

    def async_remove(self, _domain, service):
        self.removed.append(service)


class _Coordinator:
    def __init__(self, slave_id: int = 10, effective_batch: int = 4):
        self.async_write_register = AsyncMock(return_value=True)
        self.async_request_refresh = AsyncMock()
        self.data = {}
        self.device_client = SimpleNamespace(
            scan_uart_settings=False,
            effective_batch=effective_batch,
            timeout=10,
            retry=3,
            unknown_registers={},
            scanned_registers={},
            device_scan_result=None,
            config=SimpleNamespace(
                host="192.168.1.10",
                port=502,
                slave_id=slave_id,
            ),
        )


def _make_hass(coordinator=None):
    hass = SimpleNamespace()
    hass.services = _Services()
    hass.data = {}
    hass.bus = SimpleNamespace(async_fire=MagicMock())
    if coordinator is not None:
        from custom_components.thessla_green_modbus.const import DOMAIN

        hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


def _make_call(data: dict):
    return SimpleNamespace(data=data)


async def _setup_and_get(hass, service_name, coordinator, monkeypatch):
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coordinator)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    return hass.services.handlers[service_name]


def _make_scan_result(register_count: int = 5) -> dict:
    return {
        "register_count": register_count,
        "unknown_registers": {"input_registers": {99: 0}},
        "available_registers": {"input_registers": {"version_major"}, "holding_registers": set()},
        "missing_registers": {},
        "failed_addresses": {
            "modbus_exceptions": {"input_registers": set(), "holding_registers": set()}
        },
    }


def _mock_scanner_create(scan_result: dict | None = None):
    """Return (mock_scanner, mock_create_fn) pair."""
    result = scan_result or _make_scan_result()
    mock_scanner = AsyncMock()
    mock_scanner.scan_device = AsyncMock(return_value=result)
    mock_scanner.close = AsyncMock()
    mock_create = AsyncMock(return_value=mock_scanner)
    return mock_scanner, mock_create


# ---------------------------------------------------------------------------
# scan_all_registers — slave_id is passed to scanner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers_uses_slave_id(monkeypatch):
    """scan_all_registers passes coordinator.device_client.config.slave_id to the scanner factory."""
    coord = _Coordinator(slave_id=10)
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    _, kwargs = mock_create.call_args
    assert kwargs["slave_id"] == 10


# ---------------------------------------------------------------------------
# scan_all_registers — max_registers_per_request is respected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers_max_registers_passed(monkeypatch):
    """scan_all_registers passes max_registers_per_request from call data."""
    coord = _Coordinator(effective_batch=16)
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"], "max_registers_per_request": 2}))

    _, kwargs = mock_create.call_args
    assert kwargs["max_registers_per_request"] == 2


@pytest.mark.asyncio
async def test_scan_all_registers_defaults_to_coordinator_batch(monkeypatch):
    """scan_all_registers falls back to coordinator.effective_batch when not specified."""
    coord = _Coordinator(effective_batch=4)
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    _, kwargs = mock_create.call_args
    assert kwargs["max_registers_per_request"] == 4


# ---------------------------------------------------------------------------
# scan_all_registers — delay is passed to scanner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers_delay_passed(monkeypatch):
    """scan_all_registers passes delay_between_requests_ms to the scanner factory."""
    coord = _Coordinator()
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"], "delay_between_requests_ms": 200}))

    _, kwargs = mock_create.call_args
    assert kwargs["delay_between_requests_ms"] == 200


@pytest.mark.asyncio
async def test_scan_all_registers_default_delay_zero(monkeypatch):
    """scan_all_registers defaults delay to 0 (backward-compatible)."""
    coord = _Coordinator()
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    _, kwargs = mock_create.call_args
    assert kwargs["delay_between_requests_ms"] == 0


# ---------------------------------------------------------------------------
# scan_all_registers — known_registers_only maps to full_register_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers_known_only_sets_full_scan_false(monkeypatch):
    """known_registers_only=True disables full_register_scan (named scan only)."""
    coord = _Coordinator()
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"], "known_registers_only": True}))

    _, kwargs = mock_create.call_args
    assert kwargs["full_register_scan"] is False


@pytest.mark.asyncio
async def test_scan_all_registers_default_full_scan_enabled(monkeypatch):
    """Default scan uses full_register_scan=True (backward-compatible)."""
    coord = _Coordinator()
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    _, kwargs = mock_create.call_args
    assert kwargs["full_register_scan"] is True


# ---------------------------------------------------------------------------
# scan_all_registers — no writes performed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers_no_writes(monkeypatch):
    """scan_all_registers never calls async_write_register."""
    coord = _Coordinator()
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    coord.async_write_register.assert_not_awaited()


# ---------------------------------------------------------------------------
# scan_all_registers — backward-compat: result stored and summary returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers_backward_compat(monkeypatch):
    """Default scan_all_registers behavior is unchanged when no new params given."""
    coord = _Coordinator()
    hass = _make_hass()
    scan_result = _make_scan_result(register_count=10)
    _mock_scanner, mock_create = _mock_scanner_create(scan_result)

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    assert result is not None
    assert "climate.dev" in result
    assert result["climate.dev"]["summary"]["register_count"] == 10
    assert coord.device_client.device_scan_result == scan_result


# ---------------------------------------------------------------------------
# orchestration — delay_between_requests_ms triggers asyncio.sleep
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestration_delay_called_between_reads():
    """_run_word_phase calls asyncio.sleep when delay_between_requests_ms > 0."""
    from custom_components.thessla_green_modbus.scanner.orchestration import _run_word_phase

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    scanner = SimpleNamespace(
        effective_batch=4,
        delay_between_requests_ms=200,
        failed_addresses={
            "modbus_exceptions": {"input_registers": set()},
            "invalid_values": {"input_registers": set()},
        },
        available_registers={"input_registers": set()},
        _registers={4: {}},
        _names_by_address={4: {}},
    )
    scanner._alias_names = lambda func, addr: set()
    scanner._is_valid_register_value = lambda name, value: False
    scanner._log_invalid_value = lambda name, value: None

    read_calls: list[tuple] = []

    async def mock_read(start, count):
        read_calls.append((start, count))
        return [0] * count

    unknown: dict = {"input_registers": {}}
    scanned: dict = {"input_registers": 0}

    with patch("asyncio.sleep", side_effect=fake_sleep):
        await _run_word_phase(
            scanner,
            max_addr=7,
            scan_key="input_registers",
            func=4,
            read_fn=mock_read,
            unknown_registers=unknown,
            scanned_registers=scanned,
        )

    assert len(read_calls) >= 2, "Expected at least 2 batch reads for addresses 0-7"
    assert len(sleep_calls) == len(read_calls), "sleep called once per read"
    assert all(abs(s - 0.2) < 1e-9 for s in sleep_calls), "sleep duration is 200ms"


@pytest.mark.asyncio
async def test_orchestration_no_delay_when_zero():
    """_run_word_phase does NOT call asyncio.sleep when delay is 0."""
    from custom_components.thessla_green_modbus.scanner.orchestration import _run_word_phase

    sleep_calls: list = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    scanner = SimpleNamespace(
        effective_batch=4,
        delay_between_requests_ms=0,
        failed_addresses={
            "modbus_exceptions": {"input_registers": set()},
            "invalid_values": {"input_registers": set()},
        },
        available_registers={"input_registers": set()},
        _registers={4: {}},
        _names_by_address={4: {}},
    )
    scanner._alias_names = lambda func, addr: set()
    scanner._is_valid_register_value = lambda name, value: False
    scanner._log_invalid_value = lambda name, value: None

    async def mock_read(start, count):
        return [0] * count

    with patch("asyncio.sleep", side_effect=fake_sleep):
        await _run_word_phase(
            scanner,
            max_addr=7,
            scan_key="input_registers",
            func=4,
            read_fn=mock_read,
            unknown_registers={"input_registers": {}},
            scanned_registers={"input_registers": 0},
        )

    assert sleep_calls == [], "No sleep when delay is 0"


# ---------------------------------------------------------------------------
# orchestration — exception code 2 is classified as unsupported, not fatal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestration_exception_code2_not_fatal():
    """When read_fn returns None (exception code 2), scan continues without raising."""
    from custom_components.thessla_green_modbus.scanner.orchestration import _run_word_phase

    scanner = SimpleNamespace(
        effective_batch=4,
        delay_between_requests_ms=0,
        failed_addresses={
            "modbus_exceptions": {"input_registers": set()},
            "invalid_values": {"input_registers": set()},
        },
        available_registers={"input_registers": set()},
        _registers={4: {}},
        _names_by_address={4: {}},
    )
    scanner._alias_names = lambda func, addr: set()
    scanner._is_valid_register_value = lambda name, value: False
    scanner._log_invalid_value = lambda name, value: None

    call_count = 0

    async def mock_read(start, count):
        nonlocal call_count
        call_count += 1
        if start == 0:
            return None  # Simulate exception code 2 for first batch
        return [0] * count

    unknown: dict = {"input_registers": {}}
    scanned: dict = {"input_registers": 0}

    # Should not raise — exception code 2 is treated as unsupported range
    await _run_word_phase(
        scanner,
        max_addr=7,
        scan_key="input_registers",
        func=4,
        read_fn=mock_read,
        unknown_registers=unknown,
        scanned_registers=scanned,
    )

    # Addresses 0-3 are marked failed (exception code 2 → unsupported)
    assert len(scanner.failed_addresses["modbus_exceptions"]["input_registers"]) == 4
    # Scan continued after the failure — call_count > 1
    assert call_count > 1


# ---------------------------------------------------------------------------
# validate_known_registers — test coordinator factory
# ---------------------------------------------------------------------------


def _make_validate_coordinator(effective_batch=4, call_modbus_resp=None):
    """Create a coordinator stub for validate_known_registers tests.

    The stub includes device_client._write_lock, _register_maps, _call_modbus,
    and coordinator._ensure_connection — all required by the safe read path.
    """
    resp = call_modbus_resp
    if resp is None:
        resp = MagicMock()
        resp.registers = [42]
        resp.bits = None

    dc = SimpleNamespace(
        effective_batch=effective_batch,
        scan_uart_settings=False,
        timeout=10,
        retry=3,
        unknown_registers={},
        scanned_registers={},
        device_scan_result=None,
        slave_id=10,
        _write_lock=asyncio.Lock(),
        _transport=None,
        client=MagicMock(),
        _register_maps={
            "input_registers": {"version_major": 0, "version_minor": 1},
            "holding_registers": {"fan_speed_setpoint": 10},
            "coil_registers": {},
            "discrete_inputs": {},
        },
        _get_client_method=MagicMock(return_value=AsyncMock()),
        _call_modbus=AsyncMock(return_value=resp),
        config=SimpleNamespace(host="192.168.1.10", port=502, slave_id=10),
    )

    return SimpleNamespace(
        async_write_register=AsyncMock(return_value=True),
        async_request_refresh=AsyncMock(),
        _ensure_connection=AsyncMock(),
        data={},
        device_client=dc,
    )


# ---------------------------------------------------------------------------
# validate_known_registers — must not call scanner_create (no second connection)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_does_not_call_scanner_create(monkeypatch):
    """validate_known_registers must not call deps.scanner_create (no second connection)."""
    coord = _make_validate_coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    mock_create = AsyncMock()
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    mock_create.assert_not_awaited()


# ---------------------------------------------------------------------------
# validate_known_registers — calls _ensure_connection via coordinator (safe path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_calls_ensure_connection(monkeypatch):
    """validate_known_registers calls coordinator._ensure_connection (uses active connection)."""
    coord = _make_validate_coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    coord._ensure_connection.assert_awaited_once()


# ---------------------------------------------------------------------------
# validate_known_registers — reads via device_client._call_modbus (not a new client)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_uses_existing_client(monkeypatch):
    """validate_known_registers reads registers via device_client._call_modbus."""
    coord = _make_validate_coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    # _call_modbus is called once per non-empty register batch
    coord.device_client._call_modbus.assert_awaited()


# ---------------------------------------------------------------------------
# validate_known_registers — output shape: available_registers + summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_output_shape(monkeypatch):
    """validate_known_registers returns available_registers and summary with correct keys."""
    coord = _make_validate_coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    assert result is not None
    assert "climate.dev" in result
    entry = result["climate.dev"]
    assert "available_registers" in entry
    assert "summary" in entry
    assert "supported_count" in entry["summary"]
    assert "missing_count" in entry["summary"]


# ---------------------------------------------------------------------------
# validate_known_registers — registers marked available when read succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_marks_available_on_success(monkeypatch):
    """Registers are marked available when _call_modbus returns a non-empty response."""
    resp = MagicMock()
    resp.registers = [42]
    resp.bits = None
    coord = _make_validate_coordinator(call_modbus_resp=resp)
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    summary = result["climate.dev"]["summary"]
    assert summary["supported_count"] > 0
    assert summary["missing_count"] == 0


# ---------------------------------------------------------------------------
# validate_known_registers — registers marked missing when read raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_marks_missing_on_failure(monkeypatch):
    """Registers are marked missing when _call_modbus raises ConnectionException."""
    from pymodbus.exceptions import ConnectionException

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = AsyncMock(side_effect=ConnectionException("no connection"))
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    summary = result["climate.dev"]["summary"]
    assert summary["supported_count"] == 0
    assert summary["missing_count"] > 0


# ---------------------------------------------------------------------------
# validate_known_registers — respects delay_between_requests_ms via asyncio.sleep
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_respects_delay_ms(monkeypatch):
    """validate_known_registers calls asyncio.sleep for each batch when delay > 0."""
    coord = _make_validate_coordinator()
    hass = _make_hass()

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]

    with patch("asyncio.sleep", side_effect=fake_sleep):
        await handler(_make_call({"entity_id": ["climate.dev"], "delay_between_requests_ms": 100}))

    assert len(sleep_calls) > 0, "asyncio.sleep must be called when delay > 0"
    assert all(abs(s - 0.1) < 1e-9 for s in sleep_calls), "sleep duration must be 100ms"


# ---------------------------------------------------------------------------
# validate_known_registers — never calls async_write_register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_no_writes(monkeypatch):
    """validate_known_registers never calls async_write_register."""
    coord = _make_validate_coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    coord.async_write_register.assert_not_awaited()


# ---------------------------------------------------------------------------
# validate_known_registers — regression: no second transport while polling active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_no_second_transport_while_polling(monkeypatch):
    """Regression: validate_known_registers must not open a second Modbus connection.

    When the coordinator is actively polling via an existing transport,
    validate_known_registers must reuse the same connection under _write_lock
    rather than opening a new TCP transport (which causes transaction_id mismatch).
    """
    coord = _make_validate_coordinator()
    existing_transport = MagicMock()
    existing_transport.is_connected.return_value = True
    coord.device_client._transport = existing_transport
    coord.device_client._call_modbus = AsyncMock(return_value=MagicMock(registers=[1]))

    scanner_create_calls: list = []
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    async def tracking_scanner_create(**kwargs):
        scanner_create_calls.append(kwargs)
        mock_s = AsyncMock()
        mock_s.scan_device = AsyncMock(return_value={})
        mock_s.close = AsyncMock()
        return mock_s

    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", tracking_scanner_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]

    # Simulate concurrent polling by briefly holding _write_lock, then call validate.
    polling_started = asyncio.Event()

    async def simulate_polling():
        async with coord.device_client._write_lock:
            polling_started.set()
            await asyncio.sleep(0.01)

    poll_task = asyncio.ensure_future(simulate_polling())
    await polling_started.wait()

    validate_task = asyncio.ensure_future(handler(_make_call({"entity_id": ["climate.dev"]})))
    await asyncio.gather(poll_task, validate_task)

    # validate_known_registers must not have opened a new scanner/connection
    assert scanner_create_calls == [], (
        "validate_known_registers called scanner_create — this opens a second connection"
    )
    # The existing transport must still be the same object (not replaced)
    assert coord.device_client._transport is existing_transport


# ---------------------------------------------------------------------------
# Negative guard: scan_all_registers must use device_client.config.* not proxies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers_no_coordinator_host_proxy(monkeypatch):
    """scan_all_registers must not access coordinator.host (proxy removed).

    The coordinator stub intentionally has no .host/.port attributes.
    If production code accidentally used coordinator.host, the test would
    raise AttributeError and fail here.
    """
    coord = _Coordinator()
    assert not hasattr(coord, "host"), "legacy coordinator.host proxy must not be set"
    assert not hasattr(coord, "port"), "legacy coordinator.port proxy must not be set"

    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]
    # Must succeed without AttributeError
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    _, kwargs = mock_create.call_args
    assert kwargs["host"] == coord.device_client.config.host
    assert kwargs["port"] == coord.device_client.config.port


# ---------------------------------------------------------------------------
# Negative guard: validate_known_registers must not access coordinator.host proxy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_no_coordinator_host_proxy(monkeypatch):
    """validate_known_registers must not access coordinator.host (proxy removed).

    validate_known_registers no longer uses host/port — it reuses the active
    connection. This test verifies no AttributeError is raised on a coordinator
    stub that has no .host/.port attributes.
    """
    coord = _make_validate_coordinator()
    assert not hasattr(coord, "host"), "legacy coordinator.host proxy must not be set"
    assert not hasattr(coord, "port"), "legacy coordinator.port proxy must not be set"

    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    # Must succeed without AttributeError — host/port are not accessed
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))
    assert result is not None


# ---------------------------------------------------------------------------
# validate_known_registers — batch success marks only known names available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_batch_success_marks_known_names(monkeypatch):
    """When all batch reads succeed, all known register names are marked available."""
    resp = MagicMock()
    resp.registers = [1]
    resp.bits = None
    coord = _make_validate_coordinator(call_modbus_resp=resp)
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    summary = result["climate.dev"]["summary"]
    assert summary["supported_count"] == 3  # version_major, version_minor, fan_speed_setpoint
    assert summary["missing_count"] == 0
    # missing_by_type must be empty when nothing is missing
    assert summary["missing_by_type"] == {}


# ---------------------------------------------------------------------------
# validate_known_registers — batch failure falls back to individual reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_batch_failure_falls_back_to_individual(monkeypatch):
    """On batch failure, validate_known_registers retries each address individually.

    The stub register map has two input_registers (addr 0, 1) and one holding
    register (addr 10). When the first batch read raises, individual reads
    succeed → supported_count == 3 (not 0).
    """
    from pymodbus.exceptions import ModbusException

    good_resp = MagicMock()
    good_resp.registers = [42]
    good_resp.bits = None

    call_count = 0

    async def side_effect(fn, addr, *, count):
        nonlocal call_count
        call_count += 1
        # First call is the batch read for input_registers (count=2); make it fail.
        if call_count == 1:
            raise ModbusException("simulated batch failure")
        return good_resp

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = side_effect
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    summary = result["climate.dev"]["summary"]
    # Batch for input_registers failed, but both individual reads succeeded + holding batch ok.
    assert summary["supported_count"] == 3
    assert summary["missing_count"] == 0
    # failed_ranges must record the batch that triggered fallback
    failed_ranges = result["climate.dev"]["failed_ranges"]
    assert any(
        r["start"] == 0 and r["count"] == 2 for r in failed_ranges.get("input_registers", [])
    ), "failed_ranges must record the failed input_registers batch"


# ---------------------------------------------------------------------------
# validate_known_registers — individual fallback reduces missing_count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_individual_fallback_reduces_missing_count(monkeypatch):
    """Individual fallback recovers registers that share a batch with a failing one.

    input_registers addr 0 (version_major) succeeds individually; addr 1
    (version_minor) fails individually. Without fallback both would be missing;
    with fallback only version_minor is missing.
    """
    from pymodbus.exceptions import ConnectionException, ModbusException

    good_resp = MagicMock()
    good_resp.registers = [99]
    good_resp.bits = None

    calls: list[tuple[int, int]] = []

    async def side_effect(fn, addr, *, count):
        calls.append((addr, count))
        if count > 1:
            # Batch read → fail to trigger fallback
            raise ModbusException("batch fail")
        if addr == 0:
            return good_resp
        if addr == 1:
            raise ConnectionException("addr 1 unsupported")
        return good_resp

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = side_effect
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    summary = result["climate.dev"]["summary"]
    # version_major recovered individually; version_minor + holding both succeed
    assert summary["supported_count"] == 2  # version_major + fan_speed_setpoint
    assert summary["missing_count"] == 1  # version_minor
    missing = result["climate.dev"]["missing_registers"]
    assert "version_minor" in missing.get("input_registers", set())


# ---------------------------------------------------------------------------
# validate_known_registers — unsupported registers remain missing after fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_unsupported_remain_missing(monkeypatch):
    """Registers that fail both batch and individual reads are marked missing."""
    from pymodbus.exceptions import ModbusException

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = AsyncMock(
        side_effect=ModbusException("device does not support this register")
    )
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    summary = result["climate.dev"]["summary"]
    assert summary["supported_count"] == 0
    assert summary["missing_count"] == 3  # all three registers missing


# ---------------------------------------------------------------------------
# validate_known_registers — output includes missing_registers by type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_output_includes_missing_registers(monkeypatch):
    """Result includes missing_registers and failed_ranges per register type."""
    coord = _make_validate_coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    entry = result["climate.dev"]
    assert "missing_registers" in entry, "missing_registers must be present in output"
    assert "failed_ranges" in entry, "failed_ranges must be present in output"
    assert "missing_by_type" in entry["summary"], "missing_by_type must be in summary"
    # Backward-compatible fields must still be present
    assert "available_registers" in entry
    assert "supported_count" in entry["summary"]
    assert "missing_count" in entry["summary"]


# ---------------------------------------------------------------------------
# validate_known_registers — missing_by_type counts per register type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_missing_by_type_counts(monkeypatch):
    """missing_by_type in summary reflects per-type missing counts."""
    from pymodbus.exceptions import ModbusException

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = AsyncMock(side_effect=ModbusException("unsupported"))
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    by_type = result["climate.dev"]["summary"]["missing_by_type"]
    # input_registers has version_major (0) and version_minor (1): 2 missing
    assert by_type.get("input_registers", 0) == 2
    # holding_registers has fan_speed_setpoint (10): 1 missing
    assert by_type.get("holding_registers", 0) == 1
    # empty types must not appear in missing_by_type
    assert "coil_registers" not in by_type
    assert "discrete_inputs" not in by_type


# ---------------------------------------------------------------------------
# validate_known_registers — missing_registers are sorted lists (deterministic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_missing_names_are_sorted(monkeypatch):
    """missing_registers values are sorted lists, not sets — deterministic output."""
    from pymodbus.exceptions import ModbusException

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = AsyncMock(side_effect=ModbusException("unsupported"))
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    missing = result["climate.dev"]["missing_registers"]
    for reg_type, names in missing.items():
        assert isinstance(names, list), f"{reg_type} missing_registers must be a list, not a set"
        assert names == sorted(names), f"{reg_type} missing_registers must be sorted"


# ---------------------------------------------------------------------------
# validate_known_registers — INFO logs must not include full register name lists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_info_log_no_full_lists(monkeypatch, caplog):
    """INFO log lines must not contain individual missing register names."""
    import logging

    from pymodbus.exceptions import ModbusException

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = AsyncMock(side_effect=ModbusException("unsupported"))
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]

    with caplog.at_level(logging.INFO):
        await handler(_make_call({"entity_id": ["climate.dev"]}))

    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    for msg in info_msgs:
        assert "version_major" not in msg, f"INFO log must not contain register names: {msg}"
        assert "version_minor" not in msg, f"INFO log must not contain register names: {msg}"
        assert "fan_speed_setpoint" not in msg, f"INFO log must not contain register names: {msg}"


# ---------------------------------------------------------------------------
# validate_known_registers — DEBUG logs must include full missing register lists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_debug_log_includes_full_lists(monkeypatch, caplog):
    """DEBUG log must contain the full list of missing register names."""
    import logging

    from pymodbus.exceptions import ModbusException

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = AsyncMock(side_effect=ModbusException("unsupported"))
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]

    with caplog.at_level(logging.DEBUG, logger="custom_components.thessla_green_modbus"):
        await handler(_make_call({"entity_id": ["climate.dev"]}))

    debug_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    all_debug_text = " ".join(debug_msgs)
    assert "version_major" in all_debug_text or "version_minor" in all_debug_text, (
        "DEBUG logs must include missing register names"
    )


# ---------------------------------------------------------------------------
# validate_known_registers — summary includes retried_individual_count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_retried_individual_count(monkeypatch):
    """summary.retried_individual_count counts individual fallback reads after batch failure."""
    from pymodbus.exceptions import ModbusException

    good_resp = MagicMock()
    good_resp.registers = [42]
    good_resp.bits = None

    call_count = 0

    async def side_effect(fn, addr, *, count):
        nonlocal call_count
        call_count += 1
        # First call is the batch read for input_registers (count=2); make it fail.
        if call_count == 1:
            raise ModbusException("simulated batch failure")
        return good_resp

    coord = _make_validate_coordinator()
    coord.device_client._call_modbus = side_effect
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    # input_registers batch failed → 2 individual reads (version_major addr 0, version_minor addr 1)
    assert result["climate.dev"]["summary"]["retried_individual_count"] == 2
