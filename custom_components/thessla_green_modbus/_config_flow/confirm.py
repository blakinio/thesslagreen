"""Helpers for rendering config-flow confirmation steps."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, cast

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import translation

from ..const import (
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_PORT,
    DOMAIN,
)
from ..utils import resolve_connection_settings

_LOGGER = logging.getLogger(__name__)
_N_A = "—"  # language-neutral "not available" indicator


def _build_capabilities_lists(
    cap_cls: Any, caps_obj: Any, *, caps_to_dict: Any
) -> tuple[list[str], list[str]]:
    """Return (detected, not_detected) boolean capability name lists."""
    if dataclasses.is_dataclass(caps_obj) or isinstance(caps_obj, cap_cls):
        try:
            caps_data = cap_cls(**caps_to_dict(caps_obj))
        except (TypeError, ValueError):
            caps_data = cap_cls()
    elif isinstance(caps_obj, dict):
        try:
            caps_data = cap_cls(**caps_obj)
        except TypeError:
            caps_data = cap_cls()
    else:
        caps_data = cap_cls()

    detected: list[str] = []
    not_detected: list[str] = []
    for field in dataclasses.fields(cap_cls):
        if field.type not in (bool, "bool"):
            continue
        name = field.name.replace("_", " ").title()
        if getattr(caps_data, field.name):
            detected.append(name)
        else:
            not_detected.append(name)
    return detected, not_detected


def _summarize_address_dict(addr_dict: Any, *, exclude: dict[str, list[int]] | None = None) -> str:
    """Return a compact summary for a dict of register-type -> address lists/sets.

    When *exclude* is provided, those addresses are subtracted from the counts
    so that expected-optional failures do not inflate the user-visible error count.
    """
    if not isinstance(addr_dict, dict) or not addr_dict:
        return _N_A
    parts = []
    for reg_type, addresses in addr_dict.items():
        if not addresses:
            continue
        count = len(addresses)
        if exclude and reg_type in exclude:
            count -= len(exclude[reg_type])
        if count > 0:
            parts.append(f"{reg_type}: {count}")
    return ", ".join(parts) if parts else _N_A


def _summarize_missing_registers(missing: Any) -> str:
    """Return a summary of missing registers."""
    if not isinstance(missing, dict) or not missing:
        return _N_A
    parts = []
    for reg_type, regs in missing.items():
        if regs:
            count = len(regs) if isinstance(regs, (dict, list, set)) else 1
            parts.append(f"{reg_type}: {count}")
    return ", ".join(parts) if parts else _N_A


async def _get_translations(hass: HomeAssistant) -> dict[str, str]:
    """Load integration translations for the active language."""
    language = getattr(getattr(hass, "config", None), "language", "en")
    try:
        return cast(
            dict[str, str],
            await translation.async_get_translations(hass, language, "component", [DOMAIN]),
        )
    except (OSError, ValueError, HomeAssistantError) as err:
        _LOGGER.debug("Translation load failed: %s", err)
    except (TypeError, AttributeError, RuntimeError) as err:
        _LOGGER.exception("Unexpected error loading translations: %s", err)
    return {}


def _resolve_transport_labels(
    data: dict[str, Any],
    translations: dict[str, str],
) -> tuple[str, str, str, str, str]:
    """Return host, port, endpoint and transport label for confirmation UI."""
    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    connection_mode = data.get(CONF_CONNECTION_MODE)
    normalized_type, resolved_mode = resolve_connection_settings(
        connection_type, connection_mode, data.get(CONF_PORT, DEFAULT_PORT)
    )

    if normalized_type == CONNECTION_TYPE_RTU:
        endpoint = data.get(CONF_SERIAL_PORT, _N_A) or _N_A
        host_value = data.get(CONF_HOST, "-")
        port_value = str(data.get(CONF_PORT, DEFAULT_PORT))
        transport_label = translations.get(
            f"component.{DOMAIN}.connection_type_rtu_label", "Modbus RTU"
        )
    elif resolved_mode == CONNECTION_MODE_TCP_RTU:
        host_value = data.get(CONF_HOST, _N_A)
        port_value = str(data.get(CONF_PORT, DEFAULT_PORT))
        endpoint = f"{host_value}:{port_value}"
        transport_label = translations.get(
            f"component.{DOMAIN}.connection_type_tcp_rtu_label", "Modbus TCP RTU"
        )
    else:
        host_value = data.get(CONF_HOST, _N_A)
        port_value = str(data.get(CONF_PORT, DEFAULT_PORT))
        endpoint = f"{host_value}:{port_value}"
        transport_label = translations.get(
            f"component.{DOMAIN}.connection_mode_auto_label", "Modbus TCP (Auto)"
        )
        if resolved_mode == CONNECTION_MODE_TCP:
            transport_label = translations.get(
                f"component.{DOMAIN}.connection_type_tcp_label", "Modbus TCP"
            )

    transport = (resolved_mode or normalized_type).upper()
    return host_value, port_value, endpoint, transport_label, transport


async def build_confirmation_placeholders(
    *,
    hass: HomeAssistant,
    data: dict[str, Any],
    device_info: dict[str, Any],
    scan_result: dict[str, Any],
    cap_cls: Any,
    caps_to_dict: Any,
) -> dict[str, str]:
    """Build description placeholders used in confirm and reauth-confirm steps."""
    device_name = device_info.get("device_name", _N_A)
    firmware_version = device_info.get("firmware", _N_A)
    serial_number = device_info.get("serial_number", _N_A)

    available_registers = scan_result.get("available_registers", {})
    register_count = scan_result.get(
        "register_count",
        sum(len(regs) for regs in available_registers.values()),
    )

    scan_stats = scan_result.get("scan_stats") or {}
    total_attempts = scan_stats.get("total_attempts", _N_A)
    successful_reads = scan_stats.get("successful_reads", _N_A)
    raw_duration = scan_stats.get("scan_duration")
    scan_duration = f"{raw_duration:.1f}s" if raw_duration is not None else _N_A

    missing_registers_summary = _summarize_missing_registers(scan_result.get("missing_registers"))

    failed = scan_result.get("failed_addresses") or {}
    expected_optional = failed.get("expected_optional") or {}
    modbus_failed_summary = _summarize_address_dict(
        failed.get("modbus_exceptions"), exclude=expected_optional
    )
    # If no named Modbus errors remain but batch failures exist (deep/full scan raw ranges),
    # show a brief diagnostic note so the user knows what the deep scan found.
    if modbus_failed_summary == _N_A:
        batch_failures = failed.get("batch_failures") or {}
        total_batch = sum(len(v) for v in batch_failures.values() if v)
        if total_batch > 0:
            parts = [f"{rt}: {len(addrs)}" for rt, addrs in batch_failures.items() if addrs]
            modbus_failed_summary = (
                "deep scan: " + ", ".join(parts) + " unsupported raw ranges (named registers OK)"
            )
    invalid_values_summary = _summarize_address_dict(failed.get("invalid_values"))

    detected_caps, not_detected_caps = _build_capabilities_lists(
        cap_cls,
        scan_result.get("capabilities"),
        caps_to_dict=caps_to_dict,
    )

    translations = await _get_translations(hass)
    key = "auto_detected_note_success" if register_count > 0 else "auto_detected_note_limited"
    auto_detected_note = translations.get(
        f"component.{DOMAIN}.{key}",
        "Auto-detection successful!"
        if register_count > 0
        else "Limited auto-detection - some registers may be missing.",
    )

    host_value, port_value, endpoint, transport_label, transport = _resolve_transport_labels(
        data, translations
    )

    detected_capabilities_list = (
        "\n".join(f"- {c}" for c in detected_caps) if detected_caps else _N_A
    )
    not_detected_capabilities_list = (
        "\n".join(f"- {c}" for c in not_detected_caps) if not_detected_caps else _N_A
    )

    return {
        "host": host_value,
        "port": port_value,
        "endpoint": endpoint,
        "transport_label": transport_label,
        "transport": transport,
        "slave_id": str(data[CONF_SLAVE_ID]),
        "device_name": device_name,
        "firmware_version": firmware_version,
        "serial_number": serial_number,
        "register_count": str(register_count),
        "total_attempts": str(total_attempts),
        "successful_reads": str(successful_reads),
        "scan_duration": scan_duration,
        "missing_registers_summary": missing_registers_summary,
        "modbus_failed_summary": modbus_failed_summary,
        "invalid_values_summary": invalid_values_summary,
        "detected_capabilities_list": detected_capabilities_list,
        "not_detected_capabilities_list": not_detected_capabilities_list,
        "auto_detected_note": auto_detected_note,
    }
