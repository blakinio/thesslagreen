"""Unit tests for core/client_scanner.py::build_scanner_kwargs.

Validates that the function reads host/port/slave_id from
device_client.config (not from direct coordinator proxies).
"""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.thessla_green_modbus.core.client_scanner import build_scanner_kwargs


def _make_device_client(
    *,
    host: str = "10.0.0.1",
    port: int = 502,
    slave_id: int = 7,
    timeout: int = 10,
    retry: int = 3,
    backoff: float = 0.5,
    backoff_jitter: float | None = None,
    scan_uart_settings: bool = False,
    skip_missing_registers: bool = False,
    deep_scan: bool = False,
    max_regs: int = 16,
    safe_scan: bool = False,
    connection_type: str = "tcp",
    connection_mode: str | None = "tcp",
    serial_port: str = "",
    baud_rate: int = 9600,
    parity: str = "N",
    stop_bits: int = 1,
    hass: object = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(
            host=host,
            port=port,
            slave_id=slave_id,
            connection_type=connection_type,
            connection_mode=connection_mode,
            serial_port=serial_port,
            baud_rate=baud_rate,
            parity=parity,
            stop_bits=stop_bits,
        ),
        timeout=timeout,
        retry=retry,
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        scan_uart_settings=scan_uart_settings,
        skip_missing_registers=skip_missing_registers,
        deep_scan=deep_scan,
        effective_batch=max_regs,
        safe_scan=safe_scan,
        hass=hass,
    )


def test_build_scanner_kwargs_reads_host_from_config() -> None:
    dc = _make_device_client(host="192.0.2.5")
    kwargs = build_scanner_kwargs(dc, resolved_connection_mode=None)
    assert kwargs["host"] == "192.0.2.5"


def test_build_scanner_kwargs_reads_port_from_config() -> None:
    dc = _make_device_client(port=1502)
    kwargs = build_scanner_kwargs(dc, resolved_connection_mode=None)
    assert kwargs["port"] == 1502


def test_build_scanner_kwargs_reads_slave_id_from_config() -> None:
    dc = _make_device_client(slave_id=42)
    kwargs = build_scanner_kwargs(dc, resolved_connection_mode=None)
    assert kwargs["slave_id"] == 42


def test_build_scanner_kwargs_resolved_mode_overrides_config() -> None:
    dc = _make_device_client(connection_mode="auto")
    kwargs = build_scanner_kwargs(dc, resolved_connection_mode="tcp")
    assert kwargs["connection_mode"] == "tcp"


def test_build_scanner_kwargs_falls_back_to_config_mode_when_resolved_is_none() -> None:
    dc = _make_device_client(connection_mode="rtu_over_tcp")
    kwargs = build_scanner_kwargs(dc, resolved_connection_mode=None)
    assert kwargs["connection_mode"] == "rtu_over_tcp"


def test_build_scanner_kwargs_propagates_effective_batch() -> None:
    dc = _make_device_client(max_regs=8)
    kwargs = build_scanner_kwargs(dc, resolved_connection_mode=None)
    assert kwargs["max_registers_per_request"] == 8
