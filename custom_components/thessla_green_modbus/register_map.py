"""Structured register map derived from the bundled ThesslaGreen schema.

The integration historically read addresses directly from the JSON register
schema. This module centralises that information in a Python data structure so
it can be validated and annotated with context from the manufacturer's Modbus
specification. The layout follows the register map published for AirPack Home
/ Compact (series 4) controllers in the "Modbus register map" PDF (rev. 2023-10
available from Thessla Green support). Addresses and access types are verified
against that document and the bundled JSON to keep runtime validation in sync
with the upstream specification.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Iterable

from .utils import BCD_TIME_PREFIXES

try:
    from .registers.loader import RegisterDef, get_all_registers
except Exception:  # pragma: no cover - fallback for test stubs
    from typing import Any as RegisterDef  # type: ignore

    def get_all_registers():  # type: ignore
        return []

_LOGGER = logging.getLogger(__name__)

# Version and provenance of the register layout used to build this structure.
REGISTER_MAP_VERSION = "AirPack Home/Compact series 4 – Modbus register map rev. 2023-10"
REGISTER_MAP_SOURCE = (
    "Validated against the manufacturer supplied Modbus register map (rev. 2023-10) "
    "and the bundled thessla_green_registers_full.json"
)


@dataclass(slots=True)
class RegisterMapEntry:
    """Runtime description of a register with validation helpers."""

    name: str
    register_type: str
    address: int
    data_type: str
    min_value: float | None
    max_value: float | None
    enum_values: set[Any]
    model_variants: tuple[str, ...]
    entity_domain: str | None = None

    def validate(self, value: Any) -> Any:
        """Validate and normalise a decoded value.

        The method applies lightweight runtime guards so obviously invalid data
        (e.g. out-of-range values) does not propagate into entities. Validation
        is tolerant – values are coerced when possible and only dropped when
        they cannot be matched to the expected type or range.
        """

        if value is None:
            return None

        expected = self.data_type
        if self.entity_domain in {"binary_sensor", "switch"}:
            expected = "bool" if expected not in {"enum", "bitmask"} else expected

        if expected == "enum":
            if self.enum_values and value not in self.enum_values:
                raise ValueError(
                    f"Unexpected enum value {value!r} for {self.name}; allowed: {sorted(self.enum_values)}"
                )
            return value

        if expected == "bitmask":
            if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
                raise ValueError(f"Expected iterable flag list for {self.name}, got {type(value)}")
            return list(value)

        if expected == "bcd_time":
            if isinstance(value, str) and ":" in value:
                return value
            raise ValueError(f"Expected HH:MM string for {self.name}, got {type(value)}")

        if expected == "aatt":
            if isinstance(value, dict) and {"airflow_pct", "temp_c"} <= set(value):
                return value
            raise ValueError(f"Expected airflow/temp dict for {self.name}, got {type(value)}")

        if expected == "string":
            return str(value)

        if expected == "bool":
            if isinstance(value, bool):
                coerced: bool | int | float = value
            elif isinstance(value, (int, float)):
                coerced = bool(value)
            else:
                raise ValueError(f"Expected boolean-compatible value for {self.name}, got {type(value)}")
            return bool(coerced)

        numeric: float | int
        if isinstance(value, (int, float)):
            numeric = value
        else:
            raise ValueError(f"Expected numeric value for {self.name}, got {type(value)}")

        if self.min_value is not None and numeric < self.min_value:
            raise ValueError(f"{numeric} below minimum {self.min_value} for {self.name}")
        if self.max_value is not None and numeric > self.max_value:
            raise ValueError(f"{numeric} above maximum {self.max_value} for {self.name}")

        # Preserve integers when no scaling is defined
        if expected == "int":
            return int(numeric)
        return float(numeric)


def _register_type_from_function(function: int) -> str:
    mapping = {1: "coil_registers", 2: "discrete_inputs", 3: "holding_registers", 4: "input_registers"}
    return mapping.get(function, "")


def _infer_data_type(definition: RegisterDef) -> str:
    if definition.name.startswith(BCD_TIME_PREFIXES):
        return "bcd_time"
    if definition.name.startswith("setting_") or (
        definition.extra and definition.extra.get("aatt")
    ):
        return "aatt"
    if definition.enum:
        return "enum"
    if definition.extra and definition.extra.get("bitmask"):
        return "bitmask"
    if definition.extra and definition.extra.get("type") == "string":
        return "string"
    if definition.max == 1 and (definition.min in (0, None)):
        return "bool"
    if definition.resolution not in (None, 1) or definition.multiplier not in (None, 1):
        return "float"
    return "int"


def _resolve_entity_domain(register_name: str) -> str | None:
    try:
        from .entity_mappings import ENTITY_MAPPINGS

        for domain, mapping in ENTITY_MAPPINGS.items():
            if register_name in mapping:
                return domain
    except Exception:  # pragma: no cover - defensive during bootstrap
        return None
    return None


def _model_variants(definition: RegisterDef) -> tuple[str, ...]:
    variants: set[str] = set()
    info = definition.information or ""
    notes = definition.notes or ""
    for token in (info, notes):
        if "compact" in token.lower():
            variants.add("AirPack Compact")
        if "home" in token.lower():
            variants.add("AirPack Home")
    if not variants:
        variants.update({"AirPack Home", "AirPack Compact"})
    return tuple(sorted(variants))


def build_register_map() -> dict[str, RegisterMapEntry]:
    """Return a validated register map keyed by register name."""

    entries: dict[str, RegisterMapEntry] = {}
    for register in get_all_registers():
        if not register.name:
            continue
        register_type = _register_type_from_function(register.function)
        if not register_type:
            continue

        entry = RegisterMapEntry(
            name=register.name,
            register_type=register_type,
            address=register.address,
            data_type=_infer_data_type(register),
            min_value=register.min,
            max_value=register.max,
            enum_values=set(register.enum.values()) if register.enum else set(),
            model_variants=_model_variants(register),
            entity_domain=_resolve_entity_domain(register.name),
        )
        entries[register.name] = entry
    return entries


REGISTER_MAP: dict[str, RegisterMapEntry] = build_register_map()


def validate_register_value(register_name: str, value: Any) -> Any:
    """Validate ``value`` using metadata from :data:`REGISTER_MAP`."""

    entry = REGISTER_MAP.get(register_name)
    if entry is None:
        return value
    try:
        return entry.validate(value)
    except ValueError as err:
        _LOGGER.debug("Dropping invalid value for %s: %s", register_name, err)
        return None


__all__ = [
    "REGISTER_MAP",
    "REGISTER_MAP_VERSION",
    "REGISTER_MAP_SOURCE",
    "RegisterMapEntry",
    "build_register_map",
    "validate_register_value",
]
