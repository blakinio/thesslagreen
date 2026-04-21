"""Migration export surface.

This module keeps public migration imports stable while delegating implementation
into smaller, purpose-specific modules.
"""

from ._entry_migrations import async_migrate_entry

__all__ = [
    "async_migrate_entry",
]
