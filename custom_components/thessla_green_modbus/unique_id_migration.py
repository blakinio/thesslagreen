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

    uid = unique_id.replace(":", "-")
    prefix = device_unique_id_prefix(serial_number, host, port)

    for unit in airflow_units:
        suffix = f"_{unit}"
        if uid.endswith(suffix):
            uid = uid[: -len(suffix)]
            break

    pattern_new = rf"{re.escape(prefix)}_{slave_id}_[^_]+_\d+(?:_bit\d+)?$"
    if re.fullmatch(pattern_new, uid):
        return uid

    uid_no_domain = uid[len(domain) + 1 :] if uid.startswith(f"{domain}_") else uid

    lookup = get_entity_lookup()

    def _bit_index(bit: int | None) -> int | None:
        return bit.bit_length() - 1 if bit is not None else None

    def _register_address(register: str, register_type: str | None) -> int | None:
        if register_type == "holding_registers":
            return holding_registers().get(register)
        if register_type == "input_registers":
            return input_registers().get(register)
        if register_type == "coil_registers":
            return coil_registers().get(register)
        if register_type == "discrete_inputs":
            return discrete_input_registers().get(register)
        return None

    reverse_by_address: dict[tuple[int, int | None], str] = {}
    register_to_key: dict[str, str] = {}

    for mapping_key, (mapped_register_name, mapped_register_type, bit) in lookup.items():
        register_to_key.setdefault(mapped_register_name, mapping_key)
        address = _register_address(mapped_register_name, mapped_register_type)
        if address is None:
            continue
        reverse_by_address.setdefault((address, _bit_index(bit)), mapping_key)

    match = re.match(rf".*_{slave_id}_(.+)", uid_no_domain)
    remainder = match.group(1) if match else None

    base_uid: str | None = None

    if remainder:
        match_address = re.fullmatch(r"(\d+)(?:_bit(\d+))?", remainder)
        if match_address:
            address = int(match_address.group(1))
            bit_index = int(match_address.group(2)) if match_address.group(2) else None
            resolved_key = reverse_by_address.get((address, bit_index)) or reverse_by_address.get(
                (address, None)
            )
            if resolved_key:
                bit_suffix = f"_bit{bit_index}" if bit_index is not None else ""
                base_uid = f"{slave_id}_{resolved_key}_{address}{bit_suffix}"
        else:
            resolved_key = None
            matched_register_name: str | None = None
            matched_register_type: str | None = None
            matched_bit_index: int | None = None

            if remainder in lookup:
                resolved_key = remainder
                matched_register_name, matched_register_type, bit = lookup[resolved_key]
                matched_bit_index = _bit_index(bit)
            elif remainder in register_to_key:
                resolved_key = register_to_key[remainder]
                matched_register_name, matched_register_type, bit = lookup[resolved_key]
                matched_bit_index = _bit_index(bit)

            if matched_register_name:
                address = _register_address(matched_register_name, matched_register_type)
                if address is not None:
                    bit_suffix = f"_bit{matched_bit_index}" if matched_bit_index is not None else ""
                    base_uid = f"{slave_id}_{resolved_key}_{address}{bit_suffix}"
            elif remainder == "fan":
                base_uid = f"{slave_id}_fan_0"

    if base_uid is None:
        fallback = uid_no_domain
        if not fallback.startswith(f"{prefix}_"):
            fallback = f"{prefix}_{fallback}"
        return fallback

    if base_uid.startswith(prefix):
        return base_uid

    return f"{prefix}_{base_uid}"
