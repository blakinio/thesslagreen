"""Backward-compatible migration export surface.

This module keeps public migration imports stable while delegating implementation
into smaller, purpose-specific modules.
"""

from ._entity_registry_migrations import (
    async_cleanup_legacy_fan_entity,
    async_migrate_entity_ids,
    async_migrate_unique_ids,
)
from ._entry_migrations import async_migrate_entry

__all__ = [
    "async_cleanup_legacy_fan_entity",
    "async_migrate_entity_ids",
    "async_migrate_entry",
    "async_migrate_unique_ids",
]
