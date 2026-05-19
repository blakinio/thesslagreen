"""Helpers for pre-computing coordinator register read groups."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def compute_register_groups(
    coordinator: Any,
    *,
    get_register_definition: Any,
    group_reads: Any,
    holding_batch_boundaries: frozenset[int],
) -> None:
    """Pre-compute register groups for optimized batch reading."""
    coordinator._register_groups.clear()

    for key, names in coordinator.available_registers.items():
        if not names:
            continue

        mapping = coordinator._register_maps[key]
        if coordinator.safe_scan:
            groups: list[tuple[int, int]] = []
            for reg in names:
                addr = mapping.get(reg)
                if addr is None:
                    continue
                try:
                    definition = get_register_definition(reg)
                    length = max(1, definition.length)
                except (KeyError, AttributeError, TypeError) as err:
                    _LOGGER.debug("Missing definition for %s: %s", reg, err)
                    length = 1
                except (ValueError, OSError, RuntimeError) as err:  # pragma: no cover - unexpected
                    _LOGGER.exception(
                        "Unexpected error getting definition for %s: %s",
                        reg,
                        err,
                    )
                    length = 1
                groups.append((addr, min(length, coordinator.effective_batch)))
            coordinator._register_groups[key] = groups
            continue

        addresses: list[int] = []
        for reg in names:
            addr = mapping.get(reg)
            if addr is None:
                continue
            try:
                definition = get_register_definition(reg)
                length = max(1, definition.length)
            except (KeyError, AttributeError, TypeError) as err:
                _LOGGER.debug("Missing definition for %s: %s", reg, err)
                length = 1
            except (ValueError, OSError, RuntimeError) as err:  # pragma: no cover - unexpected
                _LOGGER.exception(
                    "Unexpected error getting definition for %s: %s",
                    reg,
                    err,
                )
                length = 1
            addresses.extend(range(addr, addr + length))

        boundaries = holding_batch_boundaries if key == "holding_registers" else None
        coordinator._register_groups[key] = group_reads(
            addresses,
            max_block_size=coordinator.effective_batch,
            boundaries=boundaries,
        )

    _LOGGER.debug(
        "Pre-computed register groups: %s",
        {k: len(v) for k, v in coordinator._register_groups.items()},
    )
