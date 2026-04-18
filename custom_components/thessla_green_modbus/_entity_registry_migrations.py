"""Entity-registry migration helpers executed during config entry setup."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT

try:  # pragma: no cover - optional in tests
    from homeassistant.helpers import entity_registry as er
except (ImportError, ModuleNotFoundError, AttributeError):  # pragma: no cover - defensive
    er = None

from ._legacy import (
    BIT_ENTITY_KEYS,
    LEGACY_FAN_ENTITY_IDS,
    LEGACY_KEY_RENAMES,
    extract_key_from_unique_id,
    extract_legacy_problem_key_from_entity_id,
)
from .const import CONF_SLAVE_ID, DOMAIN, device_unique_id_prefix, migrate_unique_id

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


async def async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:  # pragma: no cover - defensive
    """Rename entity IDs from translation-based to register-key-based naming."""
    try:
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.util import slugify
    except (ImportError, ModuleNotFoundError, AttributeError):
        return

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    if entity_reg is None or device_reg is None:
        return

    coordinator = entry.runtime_data
    slave_id = getattr(coordinator, "slave_id", 1)
    entries_for_config = getattr(er, "async_entries_for_config_entry", None)
    config_entry_list: list[object] = (
        list(entries_for_config(entity_reg, entry.entry_id)) if callable(entries_for_config) else []
    )

    all_platform_entries: list[object] = []
    entities_dict = getattr(entity_reg, "entities", None)
    if entities_dict is not None:
        try:
            iter_entries = entities_dict.values() if hasattr(entities_dict, "values") else entities_dict
            all_platform_entries = [e for e in iter_entries if getattr(e, "platform", None) == DOMAIN]
        except (TypeError, AttributeError, OSError, RuntimeError):
            all_platform_entries = []

    candidates: dict[str, object] = {}
    for entity in all_platform_entries:
        candidates[entity.entity_id] = entity
    for entity in config_entry_list:
        candidates[entity.entity_id] = entity

    if not candidates:
        _LOGGER.debug(
            "entity_id migration: no entities found for domain %s (config_entry=%s)",
            DOMAIN,
            entry.entry_id,
        )
        return

    slave_marker = f"_{slave_id}_"
    detected_prefixes: set[str] = set()
    for entity in candidates.values():
        uid = getattr(entity, "unique_id", None)
        if uid and slave_marker in uid:
            idx = uid.index(slave_marker)
            candidate_prefix = uid[:idx]
            if candidate_prefix:
                detected_prefixes.add(candidate_prefix)

    if not detected_prefixes:
        host = getattr(coordinator, "host", None) or entry.data.get(CONF_HOST, "")
        port = getattr(coordinator, "port", None) or entry.data.get(CONF_PORT, 0)
        device_info = getattr(coordinator, "device_info", {}) or {}
        serial = device_info.get("serial_number")
        detected_prefixes.add(device_unique_id_prefix(serial, host, port))

    def _extract_key(unique_id: str) -> str | None:
        for prefix in detected_prefixes:
            key = extract_key_from_unique_id(unique_id, prefix, slave_id)
            if key:
                return key
        return None

    migrated: list[tuple[str, str]] = []
    skipped_no_key = 0
    skipped_no_device = 0
    skipped_ok = 0
    skipped_collision = 0
    removed_stale = 0

    for reg_entry in list(candidates.values()):
        current = entity_reg.async_get(reg_entry.entity_id)
        if current is None:
            continue

        unique_id = getattr(current, "unique_id", None) or ""
        key = _extract_key(unique_id)
        if not key:
            legacy_problem_key = extract_legacy_problem_key_from_entity_id(reg_entry.entity_id)
            if legacy_problem_key:
                try:
                    entity_reg.async_remove(reg_entry.entity_id)
                    removed_stale += 1
                except (TypeError, AttributeError, OSError, RuntimeError) as exc:
                    _LOGGER.warning(
                        "entity_id migration: could not remove stale entity %s: %s",
                        reg_entry.entity_id,
                        exc,
                    )
                continue
            skipped_no_key += 1
            continue

        key = LEGACY_KEY_RENAMES.get(key, key)
        if re.fullmatch(r"problem(?:_\d+)?", key):
            try:
                entity_reg.async_remove(reg_entry.entity_id)
                removed_stale += 1
            except (TypeError, AttributeError, OSError, RuntimeError) as exc:
                _LOGGER.warning(
                    "entity_id migration: could not remove stale entity %s: %s",
                    reg_entry.entity_id,
                    exc,
                )
            continue

        bit_match = re.search(r"_bit(\d+)$", reg_entry.unique_id)
        if bit_match:
            bit_num = int(bit_match.group(1))
            bit_key = BIT_ENTITY_KEYS.get((key, bit_num))
            if bit_key is None:
                bit_key = BIT_ENTITY_KEYS.get((key, 1 << bit_num))
            if bit_key:
                key = bit_key

        device_id = getattr(current, "device_id", None)
        if not device_id:
            skipped_no_device += 1
            continue
        device = device_reg.async_get(device_id)
        if not device or not device.name:
            skipped_no_device += 1
            continue
        device_slug = slugify(device.name)
        if not device_slug:
            skipped_no_device += 1
            continue

        platform = current.entity_id.split(".")[0]
        expected_entity_id = f"{platform}.{device_slug}_{key}"
        if current.entity_id == expected_entity_id:
            skipped_ok += 1
            continue

        existing = entity_reg.async_get(expected_entity_id)
        if existing is not None:
            existing_uid = getattr(existing, "unique_id", "") or ""
            existing_key_raw = _extract_key(existing_uid)
            existing_key = (
                LEGACY_KEY_RENAMES.get(existing_key_raw, existing_key_raw) if existing_key_raw else None
            )
            if existing_key == key:
                try:
                    entity_reg.async_remove(current.entity_id)
                except (TypeError, AttributeError, OSError, RuntimeError) as exc:
                    _LOGGER.warning(
                        "entity_id migration: could not remove orphaned %s: %s",
                        current.entity_id,
                        exc,
                    )
            else:
                skipped_collision += 1
            continue

        try:
            entity_reg.async_update_entity(current.entity_id, new_entity_id=expected_entity_id)
            migrated.append((current.entity_id, expected_entity_id))
        except (TypeError, AttributeError, OSError, RuntimeError) as exc:
            _LOGGER.warning(
                "entity_id migration: could not rename %s → %s: %s",
                current.entity_id,
                expected_entity_id,
                exc,
            )

    _LOGGER.info(
        "entity_id migration done: migrated=%d removed_stale=%d already_ok=%d no_key=%d no_device=%d collision=%d",
        len(migrated),
        removed_stale,
        skipped_ok,
        skipped_no_key,
        skipped_no_device,
        skipped_collision,
    )


async def async_cleanup_legacy_fan_entity(hass: HomeAssistant, coordinator: object) -> None:
    """Remove legacy number entity IDs replaced by the fan entity."""
    if er is None:
        return
    registry = er.async_get(hass)
    if registry is None:
        return
    new_entity_id = "fan.rekuperator_fan"
    new_unique_id = f"{getattr(coordinator, 'slave_id', 1)}_0"
    migrated = False

    for old_entity_id in LEGACY_FAN_ENTITY_IDS:
        if registry.async_get(old_entity_id):
            try:
                registry.async_update_entity(
                    old_entity_id,
                    new_entity_id=new_entity_id,
                    new_unique_id=new_unique_id,
                )
            except (TypeError, AttributeError, OSError, RuntimeError):
                registry.async_remove(old_entity_id)
            migrated = True

    if migrated:
        _LOGGER.warning(
            "Legacy fan entity detected. Migrated/removed legacy entities %s to '%s'.",
            LEGACY_FAN_ENTITY_IDS,
            new_entity_id,
        )


async def async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entity unique IDs stored in the entity registry."""
    if er is None:
        return
    registry = er.async_get(hass)
    coordinator = entry.runtime_data
    device_info = getattr(coordinator, "device_info", None)
    if not isinstance(device_info, dict):
        getter = getattr(coordinator, "get_device_info", None)
        if callable(getter):
            try:
                maybe_info = getter()
                if asyncio.iscoroutine(maybe_info):
                    maybe_info = await maybe_info
                if isinstance(maybe_info, dict):
                    device_info = maybe_info
            except (TypeError, AttributeError, OSError, RuntimeError):  # pragma: no cover - defensive
                device_info = None
    serial = device_info.get("serial_number") if isinstance(device_info, dict) else None
    host = getattr(coordinator, "host", None) or entry.data.get(CONF_HOST)
    port = getattr(coordinator, "port", None) or entry.data.get(CONF_PORT)
    slave_id = getattr(coordinator, "slave_id", None) or entry.data.get(CONF_SLAVE_ID)
    entries_for_config = getattr(er, "async_entries_for_config_entry", None)
    if not callable(entries_for_config):
        return
    for reg_entry in entries_for_config(registry, entry.entry_id):
        if registry.async_get(reg_entry.entity_id) is None:
            continue
        if reg_entry.entity_id == "fan.rekuperator_fan":
            continue
        new_unique_id = migrate_unique_id(
            reg_entry.unique_id,
            serial_number=serial,
            host=host,
            port=port,
            slave_id=slave_id,
        )
        if new_unique_id != reg_entry.unique_id:
            _LOGGER.debug(
                "Migrating unique_id for %s: %s -> %s",
                reg_entry.entity_id,
                reg_entry.unique_id,
                new_unique_id,
            )
            registry.async_update_entity(reg_entry.entity_id, new_unique_id=new_unique_id)
