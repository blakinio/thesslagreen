"""Register definition model and encode/decode helpers."""

from __future__ import annotations

import logging
import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .codec import (
    apply_output_scaling,
    coerce_scaled_input,
    decode_bitmask_value,
    decode_enum_value,
    encode_enum_value,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RegisterDef:
    """Definition of a single Modbus register."""

    function: int
    address: int
    name: str
    access: str
    description: str | None = None
    description_en: str | None = None
    unit: str | None = None
    multiplier: float = 1
    resolution: float = 1
    min: float | None = None
    max: float | None = None
    default: float | None = None
    enum: dict[int | str, Any] | None = None
    notes: str | None = None
    information: str | None = None
    extra: dict[str, Any] | None = None
    length: int = 1
    bcd: bool = False
    bits: list[Any] | None = None

    def _is_temperature(self) -> bool:
        """Return True when the register represents a temperature value."""

        if self.unit and "°" in self.unit:
            return True
        return "temperature" in self.name

    # Public alias — callers outside the loader should not depend on a
    # private name. Keep ``_is_temperature`` as the canonical implementation
    # to avoid breaking existing internal callers in registers/loader.py.
    def is_temperature(self) -> bool:
        return self._is_temperature()

    def _is_bcd_time(self) -> bool:
        """Return True when the register stores a BCD HHMM time value."""

        from ..utils import BCD_TIME_PREFIXES

        return self.bcd or self.name.startswith(BCD_TIME_PREFIXES)

    def _is_aatt(self) -> bool:
        """Return True when the register stores AATT packed airflow/temp values."""

        if self.extra and self.extra.get("aatt"):
            return True
        return self.name.startswith("setting_")

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------
    def decode(self, raw: int | Sequence[int]) -> Any:
        """Decode ``raw`` according to the register metadata."""
        if self.length > 1:
            return self._decode_multi_register(raw)

        # Defensive: handle unexpected sequence for single-register values
        if isinstance(raw, Sequence):
            raw = raw[0]
        return self._decode_single_register(raw)

    def _decode_multi_register(self, raw: int | Sequence[int]) -> Any:
        if isinstance(raw, Sequence):
            raw_list = list(raw)
        else:
            raw_list = [(raw >> (16 * (self.length - 1 - i))) & 65535 for i in range(self.length)]

        if self._is_temperature() and all(v == 32768 for v in raw_list):
            return None

        if self.extra and self.extra.get("type") == "string":
            return self._decode_string_words(raw_list)

        endianness = self.extra.get("endianness", "big") if self.extra else "big"
        words = raw_list if endianness == "big" else list(reversed(raw_list))
        data = b"".join(w.to_bytes(2, "big") for w in words)

        typ = self.extra.get("type") if self.extra else None
        if typ in {"f32", "f64"}:
            fmt = ">" if endianness == "big" else "<"
            fmt += "f" if typ == "f32" else "d"
            value = struct.unpack(fmt, data)[0]
        elif typ in {"i32", "u32", "i64", "u64"}:
            value = int.from_bytes(data, "big", signed=typ.startswith("i"))
        else:
            value = int.from_bytes(data, "big", signed=False)
        return self._apply_output_scaling(value)

    def _decode_string_words(self, raw_list: list[int]) -> str:
        encoding = self.extra.get("encoding", "ascii") if self.extra else "ascii"
        data = b"".join(w.to_bytes(2, "big") for w in raw_list)
        clean = data.rstrip(b"\x00")
        try:
            return clean.decode(encoding)
        except UnicodeDecodeError:
            _LOGGER.debug(
                "Failed to decode register %s as %s; replacing invalid bytes",
                self.name,
                encoding,
            )
            return clean.decode(encoding, errors="replace")

    def _decode_single_register(self, raw: int) -> Any:
        if self.name in {"supply_air_flow", "exhaust_air_flow"} and raw == 0xFFFF:
            return None  # CF inactive, not 65535 m3/h and not zero flow.
        if self.name == "rtc_cal":
            return (raw if raw < 128 else raw - 256) if 0 <= raw <= 255 and raw != 128 else None
        if self.name in {"cf_version", "exp_version"}:
            return f"{(raw >> 8) & 255}.{raw & 255}"
        if self.name in {"filter_supply_date_limit_get", "filter_exhaust_date_limit_get"}:
            try:
                return date(2000 + (raw >> 9), (raw >> 5) & 15, raw & 31).isoformat()
            except ValueError:
                return None
        if self.name.startswith("dac_") and not (0 <= raw <= 4095):
            return None

        if raw == 32768 and (self.function == 4 or self._is_temperature()):
            return None

        # Bitmask registers map set bits to enum labels
        if self.extra and self.extra.get("bitmask") and self.enum:
            return decode_bitmask_value(raw, self.enum)

        # Regular enum registers return the mapped label
        decoded_enum = decode_enum_value(raw, self.enum)
        if decoded_enum is not None:
            return decoded_enum

        typ = self.extra.get("type") if self.extra else None
        if typ == "i16" or self._is_temperature():
            raw = raw if raw < 32768 else raw - 65536

        value = raw

        # Combined airflow/temperature values use a custom decoding
        if self._is_aatt():
            from ..utils import decode_aatt

            decoded = decode_aatt(raw)
            return decoded

        # Schedule registers using BCD time encoding
        if self._is_bcd_time():
            from ..utils import decode_bcd_time

            # Returns None for disabled/unset slots (e.g. raw == 0xFFFF).
            # Propagate None so the coordinator stores None and the select
            # entity correctly reports the slot as unset ("unknown").
            return decode_bcd_time(raw)
        return self._apply_output_scaling(value)

    def encode(self, value: Any) -> int | list[int]:
        """Encode ``value`` into the raw register representation."""

        if self.length > 1:
            return self._encode_multi_register(value)

        if self.extra and self.extra.get("bitmask") and self.enum:
            raw_int = 0
            if isinstance(value, list | tuple | set):
                for item in value:
                    for k, v in self.enum.items():
                        if v == item:
                            raw_int |= int(k)
                            break
                return raw_int
            if isinstance(value, str):
                for k, v in self.enum.items():
                    if v == value:
                        return int(k)
            return int(value)

        if self.name == "rtc_cal":
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not -127 <= value <= 127
                or int(value) != value
            ):
                raise ValueError("RTC calibration must be an integer from -127 to 127")
            return int(value) & 255
        if self.name == "filter_change" and not isinstance(value, bool) and value in (17, 33):
            # AirPack4 command values are profile-validated by the coordinator.
            return int(value)
        if self._is_bcd_time():
            if value == "disabled":
                if self.name.startswith("schedule_"):
                    return 0xA200
                if self.name.startswith(
                    ("airing_summer_", "airing_winter_", "manual_airing_time_to_start")
                ):
                    return 0x2400
                raise ValueError(f"No documented disable command for {self.name}")
            if isinstance(value, str):
                hours, minutes = (int(x) for x in value.split(":"))
            elif isinstance(value, int):
                hours, minutes = divmod(value, 60)
            elif isinstance(value, tuple | list):
                hours, minutes = int(value[0]), int(value[1])
            else:  # pragma: no cover
                raise ValueError(f"Unsupported BCD value: {value}")
            from ..schedule_helpers import time_to_bcd

            return int(time_to_bcd(time(hours, minutes)))

        if self._is_aatt():
            if isinstance(value, dict):
                airflow = value.get("airflow_pct", value.get("airflow"))
                temp = value.get("temp_c", value.get("temp"))
            elif isinstance(value, list | tuple):
                airflow, temp = value
            else:
                raise ValueError("AATT encoding needs both airflow and temperature")
            if (
                airflow is None
                or temp is None
                or isinstance(airflow, bool)
                or isinstance(temp, bool)
            ):
                raise ValueError(f"Invalid AATT value for {self.name}: {value!r}")
            flow, temperature = float(airflow), float(temp)
            if not math.isfinite(flow) or not 10 <= flow <= 100 or not flow.is_integer():
                raise ValueError("Schedule airflow must be an integer from 10 to 100 percent")
            if (
                not math.isfinite(temperature)
                or not 10 <= temperature <= 45
                or not (temperature * 2).is_integer()
            ):
                raise ValueError("Schedule temperature must be 10..45 C in 0.5 C steps")
            return (int(flow) << 8) | int(temperature * 2)

        raw: Any = value
        if self.enum and not (self.extra and self.extra.get("bitmask")):
            raw = encode_enum_value(value, self.enum, self.name)

        try:
            num_val = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            num_val = None
        if num_val is not None:
            if self.min is not None and num_val < Decimal(str(self.min)):
                raise ValueError(f"{value} is below minimum {self.min} for {self.name}")
            if self.max is not None and num_val > Decimal(str(self.max)):
                raise ValueError(f"{value} is above maximum {self.max} for {self.name}")
            scaled = Decimal(str(raw))
            if self.resolution not in (None, 1):
                step = Decimal(str(self.resolution))
                scaled = (scaled / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
            if self.multiplier not in (None, 1):
                mult = Decimal(str(self.multiplier))
                scaled = (scaled / mult).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            raw = scaled
        typ = self.extra.get("type") if self.extra else None
        if raw is None:
            raise ValueError(f"Invalid value None for {self.name}")
        if typ == "i16":
            return int(raw) & 65535
        return int(raw)

    def _apply_output_scaling(self, value: Any) -> Any:
        return apply_output_scaling(value, self.multiplier, self.resolution)

    def _encode_multi_register(self, value: Any) -> list[int]:
        if self.extra and self.extra.get("type") == "string":
            encoding = self.extra.get("encoding", "ascii")
            data = str(value).encode(encoding)
            data = data.ljust(self.length * 2, b"\x00")
            return [int.from_bytes(data[i : i + 2], "big") for i in range(0, self.length * 2, 2)]

        endianness = self.extra.get("endianness", "big") if self.extra else "big"

        raw_val: Any = value
        if self.enum:
            if isinstance(value, str):
                for k, v in self.enum.items():
                    if v == value:
                        raw_val = int(k)
                        break
                else:
                    raise ValueError(f"Invalid enum value {value!r} for {self.name}")
            elif value not in self.enum and str(value) not in self.enum:
                raise ValueError(f"Invalid enum value {value!r} for {self.name}")

        raw_val = self._coerce_scaled_input(value=value, raw_value=raw_val)
        typ = self.extra.get("type") if self.extra else None
        if typ == "f32":
            data = struct.pack(">f" if endianness == "big" else "<f", float(raw_val))
        elif typ == "f64":
            data = struct.pack(">d" if endianness == "big" else "<d", float(raw_val))
        elif typ in {"i32", "u32", "i64", "u64"}:
            size = 4 if typ in {"i32", "u32"} else 8
            data = int(raw_val).to_bytes(size, "big", signed=typ.startswith("i"))
        else:
            data = int(raw_val).to_bytes(self.length * 2, "big", signed=False)

        words = [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]
        if endianness == "little":
            words = list(reversed(words))
        return words

    def _coerce_scaled_input(self, *, value: Any, raw_value: Any) -> Any:
        return coerce_scaled_input(
            value=value,
            raw_value=raw_value,
            minimum=self.min,
            maximum=self.max,
            multiplier=self.multiplier,
            resolution=self.resolution,
            name=self.name,
        )
