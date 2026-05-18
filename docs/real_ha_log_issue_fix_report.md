# Real HA Log Issue Fix Report

## Issues Fixed

### 1. Blocking I/O: `open()` on event loop from `mappings/_helpers.py`

**Symptom:**
```
Detected blocking call to open() inside the event loop; File: .../mappings/_helpers.py, line 100
Detected blocking call to open() inside the event loop; File: .../mappings/_helpers.py, line 120
```

**Root cause:** `_number_translation_keys()` and `_load_translation_keys()` were called on the event loop during `async_setup_entry`, causing HA's blocking-I/O detector to fire on `translations/en.json` reads.

**Fix:** `async_setup_entity_mappings(hass)` in `mappings/__init__.py` wraps `_run_build_entity_mappings()` in `hass.async_add_executor_job(...)`, ensuring all translation file reads happen in a worker thread. The `@functools.cache` decorators ensure subsequent calls are free.

**Validation:** `tests/test_no_blocking_io_setup.py` patches `Path.open` and verifies no calls occur on the event-loop thread. New regression test `test_no_blocking_translation_open_during_async_setup` repeats this check.

---

### 2. Connection test failure after using scan cache

**Symptom:**
```
Using config-flow scan cache
Device missing model and firmware
Connection test failed: Modbus transport is not connected
Failed during setup: Modbus transport is not connected
```

**Root cause (two sub-problems):**

*a) Direct-client path leaves transport=None.*  
In AUTO connection mode, `select_auto_transport` may succeed via `try_direct_client_connect`, which sets `self.client` but leaves `self._transport = None`. `run_connection_test` checked only `get_transport()` and raised `ConnectionException` when `None`, even though the connection was valid.

*b) `resolved_connection_mode` was not persisted in the scan cache.*  
On the next HA restart, the cached scan was applied but `resolved_connection_mode` was not restored. AUTO mode re-ran connection probing unnecessarily.

**Fixes:**
- `core/connection_test.py`: Added optional `get_client: Callable[[], Any] | None = None` parameter. When `transport is None` but `get_client()` returns a live client, logs debug "Connection test successful (direct client)" and returns without raising.
- `coordinator/coordinator.py` and `core/client_connection.py`: Pass `get_client=lambda: self.client` to `_run_connection_test_impl`.
- `coordinator/scan.py`: `store_scan_cache` persists `"resolved_connection_mode"` in the cache dict. `apply_scan_cache` restores `coordinator._resolved_connection_mode` from the cache when in AUTO mode.

**Real connection failures still surface:** The fix only bypasses the transport-None check when a direct client exists. If both `transport` and `client` are `None`, `ConnectionException` is still raised as before.

---

### 3. Firmware/model logging noise

#### 3a. Exception code 2 on input registers 0-15

**Symptom:**
```
WARNING Exception code 2 while reading input registers 0-15
WARNING Exception code 2 while reading input registers 4-4
```

**Root cause:** `_handle_register_error_response` in `scanner/io_read.py` only demoted code-2 responses to DEBUG when `4 <= start <= 15`, missing batch reads starting at 0 (range 0-15 is the standard firmware block read).

**Fix:** Changed condition from `4 <= start <= 15` to `end <= 15`. Batch reads of the entire firmware block (start=0, end=15) now correctly log at DEBUG.

#### 3b. Skipped unsupported firmware ranges

**Symptom:**
```
WARNING Skipping unsupported input registers 2-15 (exception code 2)
```

**Fix:** `log_skipped_ranges` in `scanner/registers.py` splits unsupported input ranges into two buckets: code-2 ranges with `end <= 15` are "expected optional firmware registers" and log at DEBUG; all others still log at WARNING.

#### 3c. "Device ThesslaGreen missing model and firmware"

**Symptom:**
```
WARNING Device ThesslaGreen missing model and firmware (192.168.1.1:502)
```

**Root cause:** `warn_missing_device_info` in `coordinator/device_info.py` always logged at WARNING. For devices where firmware registers 0-15 are unavailable (older firmware), Unknown model/firmware is expected and non-fatal.

**Fix:** Changed `logger.warning` to `logger.debug` in `warn_missing_device_info`. The device still initialises and operates correctly with entities sourced from scan cache; the reduced log level just removes the false-alarm WARNING.

**What still shows as Unknown:** Devices that genuinely cannot be identified remain Unknown. The coordinator does not suppress this from `device_info`; it simply stops WARNING about it on every setup.

---

## Validation Results

| Check | Result |
|-------|--------|
| `python -m compileall custom_components/thessla_green_modbus/` | Pass |
| `python -m ruff check custom_components/ tests/` | Pass (0 errors) |
| `python -m ruff format --check custom_components/ tests/` | Pass (0 files would reformat) |
| `python tools/validate_entity_mappings.py` | Pass (366 entities) |
| `python tools/check_translations.py` | Pass (all present) |
| `python tools/compare_registers_with_reference.py` | Pass (0 missing from integration) |
| `python tools/check_maintainability.py` | Pass (maintainability gate passed) |
| Merge conflict markers | None found |
| Blocking I/O patterns remaining | None found |
| Remaining WARNING for version_patch/Exception code 2 | None found |

---

## Unrelated Logs — Not Changed

The following warnings visible in the HA logs are from OTHER integrations and were intentionally NOT touched:
- Philips Hue (any blocking or timeout warnings)
- ESPHome (connection/sync warnings)
- Google Cloud TTS (any HTTP/auth warnings)

These are unrelated to `thessla_green_modbus` and outside the scope of this fix.

---

## Modbus Behavior — Unchanged

No Modbus register addresses, register names, entity IDs, unique IDs, service IDs, translation keys, config/options flow behavior, or Modbus write behavior was changed. The integration's external contracts are identical to the pre-fix baseline.
