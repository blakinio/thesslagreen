"""Data containers for scanner device metadata and capabilities."""

from __future__ import annotations

import collections.abc
import dataclasses
from dataclasses import dataclass, field
from typing import Any

from .const import UNKNOWN_MODEL


@dataclass(slots=True)
class ScannerDeviceInfo(collections.abc.Mapping):
    """Basic identifying information about a ThesslaGreen unit.

    The attributes are populated dynamically and accessed via ``as_dict`` in
    diagnostics; they therefore appear unused in static analysis.

    Attributes:
        device_name: User configured name reported by the unit.
        model: Reported model name used to identify the device type.
        firmware: Firmware version string for compatibility checks.
        serial_number: Unique hardware identifier for the unit.
    """

    device_name: str = "Unknown"
    model: str = UNKNOWN_MODEL
    firmware: str = "Unknown"
    serial_number: str = "Unknown"
    firmware_available: bool = True
    capabilities: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def items(self) -> Any:
        return self.as_dict().items()

    def keys(self) -> Any:
        return self.as_dict().keys()

    def values(self) -> Any:
        return self.as_dict().values()

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Any:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


@dataclass(slots=True)
class DeviceCapabilities(collections.abc.Mapping):
    """Feature flags and sensor availability detected on the device.

    Although capabilities are typically determined once during the initial scan,
    the dataclass caches the result of :meth:`as_dict` for efficiency. Any
    attribute assignment will clear this cache so subsequent calls reflect the
    new values. The capability sets are mutable; modify them via assignment to
    trigger cache invalidation.
    """

    basic_control: bool = False
    temperature_sensors: set[str] = field(default_factory=set)  # Names of temperature sensors
    flow_sensors: set[str] = field(
        default_factory=set
    )  # Airflow sensor identifiers
    special_functions: set[str] = field(
        default_factory=set
    )  # Optional feature flags
    expansion_module: bool = False
    constant_flow: bool = False
    gwc_system: bool = False
    bypass_system: bool = False
    heating_system: bool = False
    cooling_system: bool = False
    air_quality: bool = False
    weekly_schedule: bool = False
    sensor_outside_temperature: bool = False
    sensor_supply_temperature: bool = False
    sensor_exhaust_temperature: bool = False
    sensor_fpx_temperature: bool = False
    sensor_duct_supply_temperature: bool = False
    sensor_gwc_temperature: bool = False
    sensor_ambient_temperature: bool = False
    sensor_heating_temperature: bool = False
    temperature_sensors_count: int = 0
    _as_dict_cache: dict[str, Any] | None = field(init=False, repr=False, default=None)

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attribute and invalidate cached ``as_dict`` result."""
        if name != "_as_dict_cache" and getattr(self, "_as_dict_cache", None) is not None:
            object.__setattr__(self, "_as_dict_cache", None)
        object.__setattr__(self, name, value)

    def as_dict(self) -> dict[str, Any]:
        """Return capabilities as a dictionary with set values sorted.

        The result is cached on first call to avoid repeated ``dataclasses.asdict``
        invocations when capabilities are accessed multiple times.
        """

        if self._as_dict_cache is None:
            data = {k: v for k, v in dataclasses.asdict(self).items() if not k.startswith("_")}
            for key, value in data.items():
                if isinstance(value, set):
                    data[key] = sorted(value)
            object.__setattr__(self, "_as_dict_cache", data)
        cache = self._as_dict_cache
        if cache is None:
            return {}
        return cache

    def items(self) -> Any:
        return self.as_dict().items()

    def keys(self) -> Any:
        return self.as_dict().keys()

    def values(self) -> Any:
        return self.as_dict().values()

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Any:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


__all__ = ["DeviceCapabilities", "ScannerDeviceInfo"]
