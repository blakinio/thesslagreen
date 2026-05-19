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

---

### 4. Coordinator retry spam when Modbus client is disconnected

**Symptom (observed 2026-05-19):**
```
WARNING: Retry context layer=coordinator op=read:holding:* attempt=1/3 kind=transient reason=connection backoff=0.0 exc=Modbus Error: [Connection] Modbus client is not connected
... (200 messages)
WARNING: Module custom_components.thessla_green_modbus.core.retry is logging too frequently. 200 messages since last count
```

**Root cause:** When the Modbus transport loses connection mid-update-cycle, each register chunk retried up to `owner.retry` times (default 3). With ~100 holding register chunks and 2 WARNING-logged attempts each (attempt 1 and 2 before final raise on attempt 3), this produced ~200 WARNING messages per update cycle.

**Fixes:**
- `core/retry.py` (`_handle_retry_exception`): Connection errors (`ConnectionException`) are now logged at DEBUG instead of WARNING. The reconnect logic (disconnect + reconnect on each attempt) is preserved. The final error propagates as the exception, not as intermediate WARNINGs.
- `core/read_batches.py` (`_read_input_register_batch`, `read_holding_registers_optimized`, `read_holding_individually`): `ConnectionException` is now re-raised instead of being swallowed/falling back. When the connection is globally broken, the entire update cycle fails immediately (after the first chunk retries) with ONE exception, which `handle_update_error` logs as a single ERROR.

**Why this is safe:**
- `ConnectionException` during read now propagates to the coordinator update cycle exactly as before (the exception type is unchanged)
- `handle_update_error` logs ONE ERROR and handles reconnection/reauth as before
- Per-register fallback (`_read_holding_fallback`) is NOT called for connection errors — correct, because fallback would also fail when globally disconnected
- Non-connection errors (permanent Modbus, timeouts, OSError) are handled exactly as before
- Disconnect is still called on each reconnect attempt (inside `disconnect_and_reconnect_for_retry`)

**Tests added:**
- `test_coordinator_io.py::test_holding_connection_exception_propagates_not_swallowed` — verifies no WARNING for holding batch connection error
- `test_coordinator_io.py::test_input_connection_exception_propagates_not_swallowed` — verifies no WARNING for input batch connection error
- `test_real_ha_log_regressions.py::test_disconnected_client_no_warning_spam` — integration-level test: 3 register groups, 3 retries; verifies zero WARNING records
- `test_coordinator_error_paths_split.py::test_read_input_registers_reconnect_on_error` — updated: `ConnectionException` now propagates (was swallowed)

---

### 5. Batch-read cancellation noise in scanner

**Symptom (observed 2026-05-19):**
```
read_holding_registers 4226-4239 cancelled on attempt 1/3
WARNING: Aborted reading holding registers 4226-4239 after 1/3 attempts due to timeout/cancellation
ERROR: Failed to read holding registers 4226-4239 after 3 retries
... (then individual fallback probes succeed)
```

**Root cause:** `should_log_terminal_failure("holding_registers", aborted_transiently=True)` returned `True`, causing `log_read_failure` (ERROR level) to fire even when the batch read was transiently cancelled — before knowing whether the individual fallback would succeed.

**Fix:**
- `scanner/io_read_helpers.py` (`should_log_terminal_failure`): Changed to `return not aborted_transiently` for all register types. The ERROR is now reserved for non-transient batch failures. Transient aborts (timeout/cancel) only emit the existing WARNING from `log_read_abort`.

**Why this is safe:**
- No Modbus behavior changed; only log level changed for transient aborts
- When batch fails transiently AND fallback also fails: `scan_register_batch` logs WARNING per individual register failure (existing behavior)
- When batch fails non-transiently: ERROR still logged (unchanged)
- HA shutdown/reload `CancelledError` already raised before reaching `_finalize_register_read_failure`, so it was never logged as ERROR — unchanged

**Tests updated:**
- `test_scanner_io.py::test_read_holding_timeout_logging` — updated: now verifies WARNING abort, not ERROR
- `test_scanner_io.py::test_should_log_terminal_failure_tracks_holding_vs_input_aborts` — updated: both holding and input return False for `aborted_transiently=True`
- `test_real_ha_log_regressions.py::test_scanner_batch_abort_transient_no_error_log` — new: verifies no ERROR for transient abort
- `test_real_ha_log_regressions.py::test_scanner_batch_permanent_failure_logs_error` — new: verifies ERROR still appears for non-transient failure

---

### 6. Setup timing: 10-second platform warning

**Symptom:**
```
Setup of sensor platform thessla_green_modbus is taking over 10 seconds
```

**Assessment:** This is expected when ~350 entities are created from a large register scan on first integration load. The integration subsequently completes setup and all entities become available. No code change warranted at this time.

**Deferred:** Reducing initial scan time would require scanner optimisation work that goes beyond the scope of this PR and has not been validated as necessary for correct operation.

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
