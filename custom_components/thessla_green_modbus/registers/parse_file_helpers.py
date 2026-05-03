"""Helpers for reading register JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cache import _async_executor


def read_registers_json(path: Path) -> Any:
    """Read and decode register definitions JSON file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:  # pragma: no cover
        raise RuntimeError(f"Register definition file missing: {path}") from err
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as err:  # pragma: no cover
        raise RuntimeError(f"Failed to read register definitions from {path}") from err


async def async_read_registers_json(hass: Any | None, path: Path) -> Any:
    """Asynchronously read and decode register definitions JSON file."""
    try:
        raw_text = await _async_executor(hass, path.read_text, encoding="utf-8")
        return json.loads(raw_text)
    except FileNotFoundError as err:  # pragma: no cover
        raise RuntimeError(f"Register definition file missing: {path}") from err
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as err:  # pragma: no cover
        raise RuntimeError(f"Failed to read register definitions from {path}") from err
