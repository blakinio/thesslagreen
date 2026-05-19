# Final Cleanup Step Report

## Branch: claude/finish-cleanup-validation-G4uSD
## Date: 2026-05-19

---

## Summary

This report documents the sequential cleanup steps performed after real Home Assistant
device validation. All changes were made following the "one small fix at a time" rule.

---

## Real-Device Status

Real-device smoke validation was reported by the user on a physical Home Assistant
installation with a ThesslaGreen AirPack device. The integration starts, exposes
approximately 350 entities, updates entities, and exposes device_clock. Modbus TCP
works. Formal evidence artifacts (log excerpts, screenshots, commit SHA, tester, date)
are still pending from the user.

### Observed real HA log issues (2026-05-19)

The following issues were identified from actual HA log output and addressed in this PR:

1. **Retry spam when client disconnected** — `core.retry` logged 200+ WARNINGs per update cycle
2. **Batch-read cancellation ERROR** — scanner logged ERROR for transiently cancelled batch reads even when individual fallback succeeded
3. **Setup timing warning** — documented; no code change made (expected behavior for ~350 entities)

---

## Step 1 — Coordinator retry spam fix

### Files changed
- `custom_components/thessla_green_modbus/core/retry.py`
- `custom_components/thessla_green_modbus/core/read_batches.py`
- `tests/test_coordinator_error_paths_split.py` (test update)
- `tests/test_coordinator_io.py` (new tests)
- `tests/test_real_ha_log_regressions.py` (new tests)

### What changed
- `_handle_retry_exception`: `ConnectionException` now logged at DEBUG (not WARNING). Reconnect logic unchanged.
- `_read_input_register_batch`, `read_holding_registers_optimized`, `read_holding_individually`: `ConnectionException` now re-raised instead of swallowed/fallback. This aborts the batch cleanly so the update cycle surfaces ONE error.

### Why safe
- No register addresses changed
- No entity IDs changed
- No service IDs changed
- Connection error type (`ConnectionException`) is unchanged — propagates identically to `handle_update_error`
- `handle_update_error` logs ONE ERROR and handles reconnection/reauth as before
- Non-connection errors (permanent Modbus, timeouts, OSError) handled exactly as before
- Disconnect-on-retry still runs (inside `disconnect_and_reconnect_for_retry`)

### Tests run
```
pytest -q tests/ -k "coordinator or device_client or update_state or update_result or offline or io"
1 failed (pre-existing), 1264 passed, 88 warnings, 2 errors (pre-existing)
```

### Rollback plan
`git revert` the relevant commit.

---

## Step 2 — Scanner batch-read cancellation noise fix

### Files changed
- `custom_components/thessla_green_modbus/scanner/io_read_helpers.py`
- `tests/test_scanner_io.py` (test updates)
- `tests/test_real_ha_log_regressions.py` (new tests)

### What changed
- `should_log_terminal_failure`: changed from `return register_type == "holding_registers"` (when `aborted_transiently=True`) to `return not aborted_transiently`. ERROR log for transient aborts is removed; WARNING from `log_read_abort` remains.

### Why safe
- No Modbus behavior changed
- No register addresses, names, entity IDs changed
- Non-transient failures still log ERROR (unchanged)
- HA shutdown cancellation was already `CancelledError`-raised before `_finalize_register_read_failure` — no change
- Individual fallback failure logging (WARNING per register) unchanged

### Tests run
```
pytest -q tests/test_scanner_io.py tests/test_scanner_io_holding.py tests/test_scanner_io_input.py tests/test_real_ha_log_regressions.py
51 passed, 16 warnings
```

### Rollback plan
`git revert` the relevant commit.

---

## Step 3 — Documentation

Updated `docs/real_ha_log_issue_fix_report.md` with sections 4, 5, and 6 documenting the new fixes and the deferred setup-timing item.

---

## Full Validation Results

```
python -m compileall -q custom_components/thessla_green_modbus tests tools  → OK (no errors)
ruff check custom_components tests tools                                     → All checks passed
ruff check --select I custom_components tests tools                          → All checks passed
ruff format --check custom_components tests tools                            → 438 files already formatted
python tools/compare_registers_with_reference.py                            → Name mismatches on common addresses: 242 (pre-existing; register naming differs from PDF reference)
python tools/check_maintainability.py                                       → Maintainability gate passed
python tools/validate_entity_mappings.py                                    → OK: 366 entities validated
python tools/check_translations.py                                          → All translation keys present
```

### Targeted tests
```
pytest tests/ -k "retry or disconnected or io_read or scanner or fallback or logging or coordinator or offline or io"
1 failed (pre-existing: test_register_value_logging caplog assertion)
1264 passed
2 errors (pre-existing: missing hass fixture from PHCC stub)
```

### Pre-existing failures (not caused by this PR)
- `test_coordinator_device_info.py::test_register_value_logging` — caplog assertion on `raw=250` (pre-existing since before this branch)
- `test_entity_unique_id.py::test_migrate_entity_unique_ids` — missing `hass` fixture (requires full pytest-homeassistant-custom-component which needs Python >=3.13)
- `test_switch.py::test_switch_icon_fallback` — missing `hass` fixture (same reason)

---

## Safety Confirmation

- No register addresses changed ✓
- No register names changed ✓
- No entity IDs changed ✓
- No unique IDs changed ✓
- No service IDs changed ✓
- No translation keys changed ✓
- No config/options flow behavior changed ✓
- No Modbus read/write behavior changed ✓
- No compatibility shims added ✓
- dev branch not used ✓
- No modbus_helpers.py reintroduced ✓

---

## Deferred Items

### Coordinator proxy cleanup
Not performed in this PR — log regression fixes were the priority. The proxy removal
inventory exists in `docs/coordinator_proxy_removal_inventory.md`. Recommended as the
next small PR after these log fixes are validated on a real device.

### Setup timing (10-second platform warning)
No code change. Expected for ~350 entities on first load. Deferred; would require scanner
optimization analysis that is out of scope for this PR.

### Formal device validation artifacts
The user has reported physical device operation but has not yet provided log excerpts,
screenshots, or other formal evidence. This does not block the code fixes.
