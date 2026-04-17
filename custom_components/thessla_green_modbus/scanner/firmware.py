"""Firmware-oriented scanner helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..scanner_register_maps import HOLDING_REGISTERS, INPUT_REGISTERS, REGISTER_DEFINITIONS

if TYPE_CHECKING:
    from ..scanner_device_info import ScannerDeviceInfo
    from .core import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)


async def scan_firmware_info(
    scanner: ThesslaGreenDeviceScanner, info_regs: list[int], device: ScannerDeviceInfo
) -> None:
    """Parse firmware version from info_regs and update device."""
    major: int | None = None
    minor: int | None = None
    patch: int | None = None
    firmware_err: Exception | None = None

    for name in ("version_major", "version_minor", "version_patch"):
        idx = INPUT_REGISTERS.get(name)
        if idx is not None and len(info_regs) > idx:
            try:
                value = info_regs[idx]
            except (TypeError, ValueError, IndexError) as exc:
                firmware_err = exc
                continue
            except (AttributeError, RuntimeError) as exc:
                _LOGGER.exception("Unexpected firmware value error for %s: %s", name, exc)
                firmware_err = exc
                continue
            if name == "version_major":
                major = value
            elif name == "version_minor":
                minor = value
            else:
                patch = value

    if None in (major, minor, patch):
        fallback_results: dict[str, int] = {}
        for name in ("version_major", "version_minor", "version_patch"):
            current = major if name == "version_major" else minor if name == "version_minor" else patch
            if current is not None:
                continue
            probe = None
            try:
                addr = INPUT_REGISTERS.get(name)
                if addr is None:
                    continue
                try:
                    probe = (
                        await scanner._read_input(scanner._client, addr, 1, skip_cache=True)
                        if scanner._client is not None
                        else await scanner._read_input(addr, 1, skip_cache=True)
                    )
                except TypeError:
                    probe = await scanner._read_input(addr, 1, skip_cache=True)
            except (TypeError, ValueError, IndexError) as exc:
                firmware_err = exc
                continue
            except (AttributeError, RuntimeError) as exc:
                _LOGGER.exception("Unexpected firmware probe error for %s: %s", name, exc)
                firmware_err = exc
                continue
            if probe:
                fallback_results[name] = probe[0]
        major = fallback_results.get("version_major", major)
        minor = fallback_results.get("version_minor", minor)
        patch = fallback_results.get("version_patch", patch)

    missing_regs: list[str] = []
    if None in (major, minor, patch):
        for name, missing_value in (
            ("version_major", major),
            ("version_minor", minor),
            ("version_patch", patch),
        ):
            if missing_value is None and name in INPUT_REGISTERS:
                missing_regs.append(f"{name} ({INPUT_REGISTERS[name]})")

    if None not in (major, minor, patch):
        device.firmware = f"{major}.{minor}.{patch}"
    else:
        details: list[str] = []
        if missing_regs:
            details.append("missing " + ", ".join(missing_regs))
        if firmware_err is not None:
            details.append(str(firmware_err))
        msg = "Failed to read firmware version registers"
        if details:
            msg += ": " + "; ".join(details)
        _LOGGER.warning(msg)
        device.firmware_available = False


async def scan_device_identity(
    scanner: ThesslaGreenDeviceScanner, info_regs: list[int], device: ScannerDeviceInfo
) -> None:
    """Parse serial number and device name from registers into device."""
    try:
        start = INPUT_REGISTERS["serial_number"]
        parts = info_regs[start : start + REGISTER_DEFINITIONS["serial_number"].length]
        if parts:
            device.serial_number = "".join(f"{p:04X}" for p in parts)
    except (KeyError, IndexError, TypeError, ValueError) as err:
        _LOGGER.debug("Failed to parse serial number: %s", err)
    except (AttributeError, RuntimeError) as err:
        _LOGGER.exception("Unexpected error parsing serial number: %s", err)
    try:
        start = HOLDING_REGISTERS["device_name"]
        name_regs = await scanner._read_holding_block(start, REGISTER_DEFINITIONS["device_name"].length) or []
        if name_regs:
            name_bytes = bytearray()
            for reg in name_regs:
                name_bytes.append((reg >> 8) & 255)
                name_bytes.append(reg & 255)
            device.device_name = name_bytes.decode("ascii", errors="replace").rstrip("\x00")
    except (KeyError, IndexError, TypeError, ValueError) as err:
        _LOGGER.debug("Failed to parse device name: %s", err)
    except (AttributeError, UnicodeDecodeError, RuntimeError) as err:
        _LOGGER.exception("Unexpected error parsing device name: %s", err)


__all__ = ["scan_device_identity", "scan_firmware_info"]
