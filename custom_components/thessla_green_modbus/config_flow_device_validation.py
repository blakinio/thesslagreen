"""Device validation runtime helper for config flow."""

from __future__ import annotations

import asyncio
import inspect
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from .const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_DEEP_SCAN,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_STOP_BITS,
)
from .errors import CannotConnect, InvalidAuth, is_invalid_auth_error
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException


async def validate_input_impl(
    hass: Any,
    data: dict[str, Any],
    *,
    normalize_connection_type: Callable[[dict[str, Any]], str],
    validate_slave_id: Callable[[dict[str, Any]], int],
    validate_tcp_config: Callable[[dict[str, Any]], tuple[str, int]],
    validate_rtu_config: Callable[[dict[str, Any]], None],
    load_scanner_module: Callable[[Any], Awaitable[Any]],
    scanner_cls_override: Any,
    capabilities_cls_override: Any,
    run_with_retry: Callable[[Callable[[], Awaitable[Any]], int, float], Awaitable[Any]],
    call_with_optional_timeout: Callable[[Callable[[], Any], float], Awaitable[Any]],
    process_scan_capabilities: Callable[[dict[str, Any], type], dict[str, Any]],
    is_request_cancelled_error: Callable[[ModbusIOException], bool],
    classify_os_error: Callable[[OSError], str],
    should_log_timeout_traceback: Callable[[BaseException], bool],
    logger: Any,
    conf_name: str,
    conf_timeout: str,
    default_name: str,
    default_port: int,
    default_timeout: float,
    default_retry: int,
    default_deep_scan: bool,
    default_parity: str,
    default_stop_bits: int,
    connection_type_tcp: str,
    config_flow_backoff: float,
    timeout_exceptions: tuple[type[BaseException], ...],
) -> dict[str, Any]:
    """Validate user-provided connection data and return scan payload."""

    connection_type = normalize_connection_type(data)
    slave_id = validate_slave_id(data)

    name = data.get(conf_name, default_name)
    timeout = data.get(conf_timeout, default_timeout)
    host = ""
    port = default_port
    if connection_type == connection_type_tcp:
        host, port = validate_tcp_config(data)
    else:
        validate_rtu_config(data)

    module = await load_scanner_module(hass)
    scanner_cls = scanner_cls_override or module.ThesslaGreenDeviceScanner
    capabilities_cls = capabilities_cls_override or module.DeviceCapabilities

    scanner: Any | None = None
    try:
        scanner = await run_with_retry(
            lambda: scanner_cls.create(
                host=host,
                port=port,
                slave_id=slave_id,
                timeout=timeout,
                retry=default_retry,
                backoff=config_flow_backoff,
                deep_scan=data.get(CONF_DEEP_SCAN, default_deep_scan),
                connection_type=connection_type,
                connection_mode=data.get(CONF_CONNECTION_MODE),
                serial_port=data.get(CONF_SERIAL_PORT),
                baud_rate=data.get(CONF_BAUD_RATE),
                parity=data.get(CONF_PARITY, default_parity),
                stop_bits=data.get(CONF_STOP_BITS, default_stop_bits),
                hass=hass,
            ),
            default_retry,
            config_flow_backoff,
        )

        short_timeout = max(2, timeout)
        verify_cb = getattr(scanner, "verify_connection", None)
        if not callable(verify_cb):
            raise AttributeError("verify_connection")

        await run_with_retry(
            lambda: call_with_optional_timeout(verify_cb, short_timeout),
            default_retry,
            config_flow_backoff,
        )

        scan_result = await run_with_retry(
            lambda: call_with_optional_timeout(scanner.scan_device, timeout),
            default_retry,
            config_flow_backoff,
        )

        if not isinstance(scan_result, dict) or not scan_result:
            raise CannotConnect("invalid_format")

        caps_dict = process_scan_capabilities(scan_result, capabilities_cls)
        scan_result["capabilities"] = caps_dict
        device_info = scan_result.get("device_info", {})

        return {
            "title": name,
            "device_info": device_info,
            "scan_result": scan_result,
        }

    except ConnectionException as exc:
        logger.error("Connection error: %s", exc)
        logger.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("cannot_connect") from exc
    except asyncio.CancelledError:
        raise
    except ModbusIOException as exc:
        if is_request_cancelled_error(exc):
            logger.info("Modbus request cancelled during device validation.")
            raise CannotConnect("timeout") from exc
        logger.error("Modbus IO error during device validation: %s", exc)
        logger.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("io_error") from exc
    except timeout_exceptions as exc:
        logger.warning("Timeout during device validation: %s", exc)
        if should_log_timeout_traceback(exc):
            logger.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("timeout") from exc
    except ModbusException as exc:
        logger.error("Modbus error: %s", exc)
        logger.debug("Traceback:\n%s", traceback.format_exc())
        if is_invalid_auth_error(exc):
            raise InvalidAuth from exc
        raise CannotConnect("modbus_error") from exc
    except AttributeError as exc:
        logger.error("Attribute error during device validation: %s", exc)
        logger.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("missing_method") from exc
    except OSError as exc:
        reason = classify_os_error(exc)
        if reason == "dns_failure":
            logger.error("DNS resolution failed: %s", exc)
        elif reason == "connection_refused":
            logger.error("Connection refused: %s", exc)
        else:
            logger.error("Unexpected error during device validation: %s", exc)
        logger.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect(reason) from exc
    except CannotConnect:
        raise
    except (ValueError, TypeError, RuntimeError, ImportError) as exc:
        logger.error("Unexpected error during device validation: %s", exc)
        logger.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("cannot_connect") from exc
    finally:
        if scanner is not None and hasattr(scanner, "close"):
            close_result = scanner.close()
            if inspect.isawaitable(close_result):
                await close_result
