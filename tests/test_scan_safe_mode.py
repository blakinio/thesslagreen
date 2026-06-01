# mypy: ignore-errors
"""Tests for scan_all_registers safe/slow mode and validate_known_registers service."""

from __future__ import annotations

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
        self.host = "192.168.1.10"
        self.port = 502
        self.slave_id = slave_id
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
    """scan_all_registers passes coordinator.slave_id to the scanner factory."""
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
# validate_known_registers — uses full_register_scan=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_known_registers_no_full_scan(monkeypatch):
    """validate_known_registers uses full_register_scan=False (named scan only)."""
    coord = _Coordinator()
    hass = _make_hass()
    scan_result = {
        "register_count": 5,
        "unknown_registers": {},
        "available_registers": {"input_registers": {"version_major"}},
        "missing_registers": {},
        "failed_addresses": {"modbus_exceptions": {"input_registers": set()}},
    }
    _mock_scanner, mock_create = _mock_scanner_create(scan_result)

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    result = await handler(_make_call({"entity_id": ["climate.dev"]}))

    _, kwargs = mock_create.call_args
    assert kwargs["full_register_scan"] is False
    assert result is not None
    assert "climate.dev" in result


@pytest.mark.asyncio
async def test_validate_known_registers_slave_id(monkeypatch):
    """validate_known_registers uses coordinator.slave_id."""
    coord = _Coordinator(slave_id=10)
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    _, kwargs = mock_create.call_args
    assert kwargs["slave_id"] == 10


@pytest.mark.asyncio
async def test_validate_known_registers_delay_passed(monkeypatch):
    """validate_known_registers passes delay_between_requests_ms."""
    coord = _Coordinator()
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"], "delay_between_requests_ms": 150}))

    _, kwargs = mock_create.call_args
    assert kwargs["delay_between_requests_ms"] == 150


@pytest.mark.asyncio
async def test_validate_known_registers_no_writes(monkeypatch):
    """validate_known_registers never calls async_write_register."""
    coord = _Coordinator()
    hass = _make_hass()
    _mock_scanner, mock_create = _mock_scanner_create()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    from custom_components.thessla_green_modbus.services import async_setup_services

    await async_setup_services(hass)
    handler = hass.services.handlers["validate_known_registers"]
    await handler(_make_call({"entity_id": ["climate.dev"]}))

    coord.async_write_register.assert_not_awaited()
