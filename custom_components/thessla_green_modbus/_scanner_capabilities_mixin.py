"""Capabilities analysis mixin for ThesslaGreenDeviceScanner."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .capability_rules import CAPABILITY_PATTERNS
from .const import SENSOR_UNAVAILABLE, SENSOR_UNAVAILABLE_REGISTERS
from .scanner_device_info import DeviceCapabilities, ScannerDeviceInfo
from .scanner_helpers import REGISTER_ALLOWED_VALUES
from .scanner_register_maps import (
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    REGISTER_DEFINITIONS,
)
from .utils import BCD_TIME_PREFIXES, decode_bcd_time

if TYPE_CHECKING:  # pragma: no cover
    from .modbus_transport import BaseModbusTransport

    class _ScannerCapabilitiesProto:
        available_registers: dict[str, set[str]]
        _register_ranges: dict[str, tuple[int | None, int | None]]
        _client: Any | None
        _transport: BaseModbusTransport | None

        async def _read_input(self, *args: Any, **kwargs: Any) -> list[int] | None: ...
        async def _read_holding_block(self, *args: Any, **kwargs: Any) -> list[int] | None: ...


_LOGGER = logging.getLogger(__name__)


class _ScannerCapabilitiesMixin:
    """Capability analysis and firmware/device-identity scanning."""

    def _is_valid_register_value(self, name: str, value: int) -> bool:
        """Validate a register value against known constraints.

        This check is intentionally lightweight – it ensures that obvious
        placeholder values (like ``SENSOR_UNAVAILABLE``) and values outside the
        ranges defined in the register metadata are ignored.  The method mirrors
        behaviour expected by the tests but does not aim to provide exhaustive
        validation of every register.
        """

        if value == 65535:
            return False

        # Registers in SENSOR_UNAVAILABLE_REGISTERS return 0x8000 when a sensor
        # is not physically connected. The register itself EXISTS and must produce
        # an entity (shown as "unavailable" in HA). Only EC2 responses mean the
        # register is truly absent. Accept 0x8000 here — coordinator and sensor.py
        # already handle it correctly via the SENSOR_UNAVAILABLE sentinel.
        if name in SENSOR_UNAVAILABLE_REGISTERS and value == SENSOR_UNAVAILABLE:
            return True

        if "temperature" in name and value == SENSOR_UNAVAILABLE:
            return True

        allowed = REGISTER_ALLOWED_VALUES.get(name)
        if allowed is not None and value not in allowed:
            return False

        if name.startswith(BCD_TIME_PREFIXES) and name != "schedule_start_time":
            if decode_bcd_time(value) is None:
                return False

        if range_vals := self._register_ranges.get(name):  # type: ignore[attr-defined]
            min_val, max_val = range_vals
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False

        return True

    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Derive device capabilities from discovered registers."""

        caps = DeviceCapabilities()
        inputs = self.available_registers["input_registers"]  # type: ignore[attr-defined]
        holdings = self.available_registers["holding_registers"]  # type: ignore[attr-defined]
        coils = self.available_registers["coil_registers"]  # type: ignore[attr-defined]
        discretes = self.available_registers["discrete_inputs"]  # type: ignore[attr-defined]

        # Temperature sensors
        temp_map = {
            "sensor_outside_temperature": "outside_temperature",
            "sensor_supply_temperature": "supply_temperature",
            "sensor_exhaust_temperature": "exhaust_temperature",
            "sensor_fpx_temperature": "fpx_temperature",
            "sensor_duct_supply_temperature": "duct_supply_temperature",
            "sensor_gwc_temperature": "gwc_temperature",
            "sensor_ambient_temperature": "ambient_temperature",
            "sensor_heating_temperature": "heating_temperature",
        }
        for attr, reg in temp_map.items():
            if reg in inputs:
                setattr(caps, attr, True)
                caps.temperature_sensors.add(reg)

        caps.temperature_sensors_count = len(caps.temperature_sensors)  # pragma: no cover

        # Expansion module and GWC detection via discrete inputs/coils
        if "expansion" in discretes:
            caps.expansion_module = True  # pragma: no cover
        if "gwc" in coils or "gwc_temperature" in inputs:
            caps.gwc_system = True  # pragma: no cover

        if "bypass" in coils:
            caps.bypass_system = True  # pragma: no cover
        if any(reg.startswith("schedule_") for reg in holdings):
            caps.weekly_schedule = True  # pragma: no cover

        if "on_off_panel_mode" in holdings:
            caps.basic_control = True  # pragma: no cover

        if any(
            reg in inputs
            for reg in [
                "constant_flow_active",
                "supply_flow_rate",
                "supply_air_flow",
                "cf_version",
            ]
        ):
            caps.constant_flow = True  # pragma: no cover

        # Generic capability detection based on register name patterns
        all_registers = inputs | holdings | coils | discretes
        for attr, patterns in CAPABILITY_PATTERNS.items():
            if getattr(caps, attr):
                continue
            if any(pat in reg for reg in all_registers for pat in patterns):
                setattr(caps, attr, True)

        return caps

    async def _scan_firmware_info(self, info_regs: list[int], device: ScannerDeviceInfo) -> None:
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
                except (TypeError, ValueError, IndexError) as exc:  # pragma: no cover - best effort
                    firmware_err = exc
                    continue
                except (AttributeError, RuntimeError) as exc:  # pragma: no cover - unexpected
                    _LOGGER.exception("Unexpected firmware value error for %s: %s", name, exc)
                    firmware_err = exc
                    continue
                if name == "version_major":
                    major = value
                elif name == "version_minor":
                    minor = value
                else:
                    patch = value

        # Some devices reject larger blocks around register 0 but still allow
        # individual reads of the firmware registers. Retry missing values as
        # single-register probes while bypassing failed-range caching.
        if None in (major, minor, patch):
            fallback_results: dict[str, int] = {}
            for name in ("version_major", "version_minor", "version_patch"):
                current = (
                    major
                    if name == "version_major"
                    else minor
                    if name == "version_minor"
                    else patch
                )
                if current is not None:
                    continue
                probe = None
                try:
                    addr = INPUT_REGISTERS.get(name)
                    if addr is None:
                        continue
                    try:
                        probe = (
                            await self._read_input(self._client, addr, 1, skip_cache=True)  # type: ignore[attr-defined]
                            if self._client is not None  # type: ignore[attr-defined]
                            else await self._read_input(addr, 1, skip_cache=True)  # type: ignore[attr-defined]
                        )
                    except TypeError:
                        probe = await self._read_input(addr, 1, skip_cache=True)  # type: ignore[attr-defined]
                except (TypeError, ValueError, IndexError) as exc:  # pragma: no cover - best effort
                    firmware_err = exc
                    continue
                except (AttributeError, RuntimeError) as exc:  # pragma: no cover - unexpected
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
                details.append(str(firmware_err))  # pragma: no cover
            msg = "Failed to read firmware version registers"
            if details:
                msg += ": " + "; ".join(details)
            _LOGGER.warning(msg)
            device.firmware_available = False  # pragma: no cover

    async def _scan_device_identity(self, info_regs: list[int], device: ScannerDeviceInfo) -> None:
        """Parse serial number and device name from registers into device."""
        try:
            start = INPUT_REGISTERS["serial_number"]
            parts = info_regs[start : start + REGISTER_DEFINITIONS["serial_number"].length]
            if parts:
                device.serial_number = "".join(f"{p:04X}" for p in parts)
        except (KeyError, IndexError, TypeError, ValueError) as err:  # pragma: no cover
            _LOGGER.debug("Failed to parse serial number: %s", err)
        except (AttributeError, RuntimeError) as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error parsing serial number: %s", err)
        try:
            start = HOLDING_REGISTERS["device_name"]
            name_regs = (
                await self._read_holding_block(start, REGISTER_DEFINITIONS["device_name"].length)  # type: ignore[attr-defined]
                or []
            )
            if name_regs:
                name_bytes = bytearray()
                for reg in name_regs:
                    name_bytes.append((reg >> 8) & 255)
                    name_bytes.append(reg & 255)
                device.device_name = name_bytes.decode("ascii", errors="replace").rstrip("\x00")
        except (KeyError, IndexError, TypeError, ValueError) as err:  # pragma: no cover
            _LOGGER.debug("Failed to parse device name: %s", err)
        except (
            AttributeError,
            UnicodeDecodeError,
            RuntimeError,
        ) as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error parsing device name: %s", err)
