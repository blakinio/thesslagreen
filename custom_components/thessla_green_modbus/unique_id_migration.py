"""Unique-id migration helpers."""

from __future__ import annotations

import re
from collections.abc import Callable

EntityLookup = dict[str, tuple[str, str | None, int | None]]
RegisterGetter = Callable[[], dict[str, int]]


def sanitize_identifier(value: str) -> str:
    """Sanitize identifier components used inside unique IDs."""

    sanitized = re.sub(r"[^0-9A-Za-z_-]", "-", value)
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = re.sub(r"_{2,}", "_", sanitized)
    return sanitized.strip("-_")


def device_unique_id_prefix(
    serial_number: str | None,
    host: str,
    port: int | None,
) -> str:
    """Return the device specific prefix used in entity unique IDs."""

    if serial_number:
        serial_token = sanitize_identifier(serial_number)
        if serial_token:
            return serial_token

    host_part = sanitize_identifier(host.replace(":", "-")) if host else ""
    port_part = sanitize_identifier(str(port)) if port is not None else ""

    if host_part and port_part:
        return f"{host_part}-{port_part}"
    if host_part:
        return host_part
    if port_part:
        return f"device-{port_part}"
    return "device"


def _parse_legacy_unique_id(uid: str, airflow_units: tuple[str, str]) -> str:
    """Strip airflow unit suffix from uid if present."""
    for unit in airflow_units:
        if uid.endswith(f"_{unit}"):
            return uid[: -len(unit) - 1]
    return uid


def _should_migrate_unique_id(uid: str, prefix: str, slave_id: int) -> bool:
    """Return True if uid already matches the current format — no migration needed."""
    pattern = rf"{re.escape(prefix)}_{slave_id}_[^_]+_\d+(?:_bit\d+)?$"
    return bool(re.fullmatch(pattern, uid))


def _resolve_legacy_register_name(
    remainder: str,
    lookup: EntityLookup,
    register_to_key: dict[str, str],
    get_address: Callable[[str, str | None], int | None],
    slave_id: int,
) -> str | None:
    """Resolve a name-based legacy remainder to a base_uid, or None."""
    resolved_key: str | None = None
    if remainder in lookup:
        resolved_key = remainder
    elif remainder in register_to_key:
        resolved_key = register_to_key[remainder]

    if resolved_key is not None:
        reg_name, reg_type, bit = lookup[resolved_key]
        address = get_address(reg_name, reg_type)
        if address is not None:
            bit_idx = bit.bit_length() - 1 if bit is not None else None
            bit_suffix = f"_bit{bit_idx}" if bit_idx is not None else ""
            return f"{slave_id}_{resolved_key}_{address}{bit_suffix}"

    if remainder == "fan":
        return f"{slave_id}_fan_0"
    return None


def _resolve_legacy_entity_parts(
    uid_no_domain: str,
    slave_id: int,
    lookup: EntityLookup,
    get_address: Callable[[str, str | None], int | None],
) -> str | None:
    """Return base_uid by resolving a legacy uid against register maps, or None."""
    reverse_by_address: dict[tuple[int, int | None], str] = {}
    register_to_key: dict[str, str] = {}
    for key, (reg_name, reg_type, bit) in lookup.items():
        register_to_key.setdefault(reg_name, key)
        address = get_address(reg_name, reg_type)
        if address is not None:
            bit_idx = bit.bit_length() - 1 if bit is not None else None
            reverse_by_address.setdefault((address, bit_idx), key)

    match = re.match(rf".*_{slave_id}_(.+)", uid_no_domain)
    if not match:
        return None
    remainder = match.group(1)

    addr_match = re.fullmatch(r"(\d+)(?:_bit(\d+))?", remainder)
    if addr_match:
        address = int(addr_match.group(1))
        bit_idx = int(addr_match.group(2)) if addr_match.group(2) else None
        key = reverse_by_address.get((address, bit_idx)) or reverse_by_address.get((address, None))
        if key:
            bit_suffix = f"_bit{bit_idx}" if bit_idx is not None else ""
            return f"{slave_id}_{key}_{address}{bit_suffix}"
        return None

    return _resolve_legacy_register_name(remainder, lookup, register_to_key, get_address, slave_id)


def _build_migrated_unique_id(base_uid: str | None, prefix: str, uid_no_domain: str) -> str:
    """Assemble the final migrated unique ID from resolved parts."""
    if base_uid is None:
        fallback = uid_no_domain
        if not fallback.startswith(f"{prefix}_"):
            fallback = f"{prefix}_{fallback}"
        return fallback
    if base_uid.startswith(prefix):
        return base_uid
    return f"{prefix}_{base_uid}"


def migrate_unique_id(
    unique_id: str,
    *,
    serial_number: str | None,
    host: str,
    port: int,
    slave_id: int,
    domain: str,
    airflow_units: tuple[str, str],
    get_entity_lookup: Callable[[], EntityLookup],
    holding_registers: RegisterGetter,
    input_registers: RegisterGetter,
    coil_registers: RegisterGetter,
    discrete_input_registers: RegisterGetter,
) -> str:
    """Migrate a historical unique_id to the current format."""

    uid = _parse_legacy_unique_id(unique_id.replace(":", "-"), airflow_units)
    prefix = device_unique_id_prefix(serial_number, host, port)

    if _should_migrate_unique_id(uid, prefix, slave_id):
        return uid

    uid_no_domain = uid[len(domain) + 1 :] if uid.startswith(f"{domain}_") else uid
    lookup = get_entity_lookup()

    def _get_address(register: str, register_type: str | None) -> int | None:
        if register_type == "holding_registers":
            return holding_registers().get(register)
        if register_type == "input_registers":
            return input_registers().get(register)
        if register_type == "coil_registers":
            return coil_registers().get(register)
        if register_type == "discrete_inputs":
            return discrete_input_registers().get(register)
        return None

    base_uid = _resolve_legacy_entity_parts(uid_no_domain, slave_id, lookup, _get_address)
    return _build_migrated_unique_id(base_uid, prefix, uid_no_domain)
