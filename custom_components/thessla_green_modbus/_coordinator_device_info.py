"""Coordinator helpers for scan lifecycle and device-info warnings."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from .modbus_exceptions import ConnectionException, ModbusException


async def run_device_scan(
    *,
    create_scanner: Any,
    apply_scan_result: Any,
    logger: logging.Logger,
) -> None:
    """Run full scan, apply result and always close scanner."""

    logger.info("Scanning device for available registers...")
    scanner = None
    try:
        scanner = await create_scanner()
        scan_result = scanner.scan_device()
        if inspect.isawaitable(scan_result):
            scan_result = await scan_result
        apply_scan_result(scan_result)
    except asyncio.CancelledError:
        logger.warning("Device scan cancelled")
        raise
    except (ModbusException, ConnectionException) as exc:
        logger.exception("Device scan failed: %s", exc)
        raise
    except TimeoutError as exc:
        logger.warning("Device scan timed out: %s", exc)
        raise
    except (OSError, ValueError) as exc:
        logger.exception("Unexpected error during device scan: %s", exc)
        raise
    finally:
        if scanner is not None:
            close_result = scanner.close()
            if inspect.isawaitable(close_result):
                await close_result


def warn_missing_device_info(
    *,
    device_info: dict[str, Any],
    config: Any,
    device_name: str,
    logger: logging.Logger,
    unknown_model: str,
) -> None:
    """Warn when model or firmware could not be identified."""

    model = device_info.get("model", unknown_model)
    firmware = device_info.get("firmware", "Unknown")
    if model != unknown_model and firmware != "Unknown":
        return

    missing: list[str] = []
    if model == "Unknown":
        missing.append("model")
        logger.debug(
            "Device model missing for %s:%s%s",
            config.host,
            config.port,
            f" (slave {config.slave_id})" if config.slave_id is not None else "",
        )
    if firmware == "Unknown":
        missing.append("firmware")
        logger.debug(
            "Device firmware missing for %s:%s%s",
            config.host,
            config.port,
            f" (slave {config.slave_id})" if config.slave_id is not None else "",
        )
    if missing:
        device_details = f"{config.host}:{config.port}"
        if config.slave_id is not None:
            device_details += f", slave {config.slave_id}"
        logger.warning(
            "Device %s missing %s (%s). "
            "Verify Modbus connectivity or ensure your firmware is supported.",
            device_name,
            " and ".join(missing),
            device_details,
        )
