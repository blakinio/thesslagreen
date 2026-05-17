"""Tests proving that mapping setup does not perform blocking file I/O on the event loop.

Three invariants are verified:
1. Entity mapping output is identical across independent rebuild calls.
2. Translation keys are correctly loaded and non-empty.
3. pathlib.Path.open is never called from within the async event-loop thread
   when async_setup_entity_mappings(hass) is used.
"""

from __future__ import annotations

import asyncio
import copy
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import custom_components.thessla_green_modbus.mappings as em
import pytest
from custom_components.thessla_green_modbus.mappings._helpers import (
    _load_translation_keys,
    _number_translation_keys,
)

# ---------------------------------------------------------------------------
# 1. Mapping output stability
# ---------------------------------------------------------------------------


def test_entity_mapping_output_is_stable_across_rebuilds() -> None:
    """Rebuilding mappings twice must produce identical output."""
    em._run_build_entity_mappings()
    snapshot_a = copy.deepcopy(em.ENTITY_MAPPINGS)

    em._run_build_entity_mappings()
    snapshot_b = copy.deepcopy(em.ENTITY_MAPPINGS)

    assert snapshot_a == snapshot_b, "ENTITY_MAPPINGS changed between two consecutive builds"


def test_number_entity_mappings_non_empty_after_build() -> None:
    """NUMBER_ENTITY_MAPPINGS must be populated after a build."""
    em._run_build_entity_mappings()
    assert em.NUMBER_ENTITY_MAPPINGS, "NUMBER_ENTITY_MAPPINGS is empty after build"


def test_entity_mappings_contains_expected_domains() -> None:
    """ENTITY_MAPPINGS must contain all expected platform keys after build."""
    em._run_build_entity_mappings()
    expected = {"number", "sensor", "binary_sensor", "switch", "select", "text", "time"}
    missing = expected - set(em.ENTITY_MAPPINGS)
    assert not missing, f"ENTITY_MAPPINGS missing domains: {missing}"


# ---------------------------------------------------------------------------
# 2. Translation key loading
# ---------------------------------------------------------------------------


def test_number_translation_keys_non_empty() -> None:
    """_number_translation_keys() must return a non-empty set."""
    keys = _number_translation_keys()
    assert isinstance(keys, set)
    assert len(keys) > 0, "_number_translation_keys() returned an empty set"


def test_load_translation_keys_non_empty() -> None:
    """_load_translation_keys() must return non-empty sets for known entity types."""
    keys = _load_translation_keys()
    assert isinstance(keys, dict)
    for domain in ("binary_sensor", "switch", "select"):
        assert domain in keys, f"Missing domain '{domain}' in translation keys"
        assert len(keys[domain]) > 0, f"Empty translation key set for domain '{domain}'"


def test_translation_keys_match_entity_mappings() -> None:
    """Every translation_key value in ENTITY_MAPPINGS must appear in en.json."""
    em._run_build_entity_mappings()
    trans = _load_translation_keys()
    num_keys = _number_translation_keys()

    domain_trans: dict[str, set[str]] = {
        "binary_sensor": trans["binary_sensor"],
        "switch": trans["switch"],
        "select": trans["select"],
        "number": num_keys,
    }

    for domain, entries in em.ENTITY_MAPPINGS.items():
        if domain not in domain_trans:
            continue
        known = domain_trans[domain]
        for key, defn in entries.items():
            tk = defn.get("translation_key", key)
            assert tk in known, f"translation_key '{tk}' for {domain}.{key} not found in en.json"


# ---------------------------------------------------------------------------
# 3. No blocking Path.open from event-loop thread
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_entity_mappings_no_path_open_in_event_loop() -> None:
    """Path.open must never be called from the event-loop thread during setup.

    The fix ensures that all file I/O (translation JSON loading) happens inside
    async_add_executor_job, i.e. in a worker thread rather than the event loop.
    """
    # Clear the translation-key caches so that actual file reads happen during
    # this test run (verifying the executor path, not the cached path).
    _number_translation_keys.cache_clear()
    _load_translation_keys.cache_clear()

    event_loop_thread = threading.current_thread()
    open_calls_on_loop_thread: list[str] = []

    original_open = Path.open

    def _tracking_open(self: Path, *args: object, **kwargs: object):  # type: ignore[override]
        if threading.current_thread() is event_loop_thread:
            open_calls_on_loop_thread.append(str(self))
        return original_open(self, *args, **kwargs)

    mock_hass = MagicMock()

    async def _executor_job(fn, *args):
        """Simulate async_add_executor_job using a real thread-pool executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args)

    mock_hass.async_add_executor_job = _executor_job

    with patch.object(Path, "open", _tracking_open):
        await em.async_setup_entity_mappings(hass=mock_hass)

    assert not open_calls_on_loop_thread, (
        "Path.open was called from the event-loop thread during mapping setup: "
        + ", ".join(open_calls_on_loop_thread)
    )

    # Restore caches for subsequent tests
    _number_translation_keys.cache_clear()
    _load_translation_keys.cache_clear()
    em._run_build_entity_mappings()
