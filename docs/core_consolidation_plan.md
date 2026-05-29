# Core Package Consolidation Plan

**Status: Planning only — no code merged in this document**
**Created: 2026-05-29**
**Related PR: #1685 (docs/refactor: plan pymodbus 4 migration and reduce core complexity)**

---

## 1. Current Layout Inventory

The `core/` package currently has 25 Python files. They are grouped by concern below.

### 1.1 Main client entry point

| File | Concern |
|---|---|
| `client.py` | `ThesslaGreenDeviceClient` — assembles all mixins into the main device client |

### 1.2 Connection concern

| File | Concern |
|---|---|
| `connection.py` | High-level connection helpers shared by client and scanner |
| `connection_lifecycle.py` | Async connection open/close logic |
| `connection_state.py` | Connection state tracking (connected, offline, etc.) |
| `connection_test.py` | Register-probe helpers for connection validation |
| `disconnect.py` | Disconnect / teardown helpers |
| `transport_select.py` | Transport selection logic (TCP vs RTU, mode detection) |

### 1.3 Read path concern

| File | Concern |
|---|---|
| `read_batches.py` | Batched multi-register reads |
| `read_bits.py` | Coil / discrete input reads |
| `read_common.py` | Shared read infrastructure (retry wrappers, error helpers) |
| `runtime_io.py` | High-level runtime read/write dispatcher |
| `io_mixin.py` | `_ModbusIOMixin` — Modbus read protocol mixin used by DeviceClient |

### 1.4 Write path concern

| File | Concern |
|---|---|
| `write_path.py` | Write operations (single register, multi-register, coil writes) |

### 1.5 Scanner support

| File | Concern |
|---|---|
| `client_scanner.py` | `_DeviceClientScannerMixin` — scanner orchestration methods |
| `scan_helpers.py` | Scan result processing helpers |
| `scanner_kwargs.py` | Scanner construction argument assembly |

### 1.6 Capability / model / config helpers

| File | Concern |
|---|---|
| `capabilities_mixin.py` | `_CoordinatorCapabilitiesMixin` — derived capability metrics |
| `models.py` | `CoordinatorConfig` and related data models |
| `register_groups.py` | Register group grouping and iteration helpers |
| `register_processing.py` | Register value post-processing (scaling, enum decode, etc.) |

### 1.7 Runtime / config / state helpers

| File | Concern |
|---|---|
| `client_connection.py` | `_DeviceClientConnectionMixin` — connection lifecycle mixin |
| `client_registers.py` | `_DeviceClientRegistersMixin` — register IO helpers mixin |
| `retry.py` | Retry/backoff utilities |
| `runtime_state.py` | Runtime state snapshot helpers |

---

## 2. Recommended Target Layout

The long-term target layout reduces the file count while preserving logical separation:

```
core/
  __init__.py
  client.py              # ThesslaGreenDeviceClient (unchanged — assembles mixins)
  models.py              # CoordinatorConfig, data models (unchanged)
  connection/            # or connection.py if small enough
    __init__.py          # re-exports public symbols
    lifecycle.py         # open/close/teardown (from connection_lifecycle, disconnect)
    state.py             # connection state (from connection_state)
    test.py              # connection probe (from connection_test)
    transport_select.py  # transport selection (from transport_select)
  read/                  # or read.py if small enough
    __init__.py
    batches.py           # from read_batches
    bits.py              # from read_bits
    common.py            # from read_common
    io_mixin.py          # _ModbusIOMixin (from io_mixin)
    runtime_io.py        # from runtime_io
  write.py               # from write_path (already focused)
  register_processing.py # unchanged
  register_groups.py     # unchanged
  retry.py               # unchanged
  scan_helpers.py        # unchanged
  scanner_kwargs.py      # unchanged
  capabilities_mixin.py  # unchanged
  client_connection.py   # unchanged until connection/ package is ready
  client_scanner.py      # unchanged
  client_registers.py    # unchanged
```

### Notes on target layout

- Do not merge `client.py` into a monolith — keep it as the assembler of mixins.
- The `connection/` sub-package makes sense because there are 6 connection-related files.
- The `read/` sub-package may be deferred if the file count is manageable.
- Circular imports are the primary risk; always verify with `python -m compileall` after moves.

---

## 3. Consolidation Rules

These rules apply to every consolidation slice:

1. **Preserve public imports** — if a module is imported by name outside `core/`, keep the old
   name as a re-export shim for one PR cycle, then remove it in the next.
   Exception: purely internal helpers with no external import are safe to move immediately.

2. **No behavior changes** — consolidation is file moves only. No logic changes.

3. **Use `git mv`** — preserves history. Never copy-paste.

4. **One concern per PR** — do not mix connection and read consolidation in the same PR.

5. **Run full validation after every slice** — see the validation checklist at the bottom.

6. **Avoid actively-touched files** — if a file was modified in the last 3 PRs or is
   referenced in a real-device fix, defer its consolidation.

7. **No shims** — per `docs/thesslagreen_guidelines.md`, compatibility shims are forbidden.
   Update all import sites instead of adding re-export modules.

---

## 4. Suggested Safe Slices

### Slice 0 — Documentation only (this PR)

- Create this document.
- Identify the safest first move.
- No code changed.

### Slice 1 — Tiny internal-only helper (optional, this PR)

If a module under `core/` is:
- fewer than 40 lines,
- imported only within `core/` itself (no external callers),
- logically owned by a single larger module,

it may be inlined into its owning module in this PR.

**Candidates assessed:**

| File | Lines | External imports? | Assessment |
|---|---|---|---|
| `scanner_kwargs.py` | ~35 | `core/client_scanner.py` only | Potentially safe — see Slice 1 notes |
| `retry.py` | ~40 | `core/connection.py` only | Potentially safe |
| `runtime_state.py` | ~30 | `core/client_registers.py` only | Potentially safe |

Assessment is preliminary. Before performing any move:
- Run `grep -r "from.*core.*<module>" custom_components tests tools` to confirm no external callers.
- If any external caller is found, defer.

**Deferred from this PR:** No code consolidation was performed in this PR. All three candidates
above require a grep audit and import-site update that should be done as a standalone slice
with focused tests. See "Deferred work" in the PR body.

### Slice 2 — Connection helper consolidation

Target: merge `connection_state.py` and `disconnect.py` into `connection_lifecycle.py`
(or into a `connection/` sub-package).

Prerequisites:
- Real-device validation after #1684 must be complete.
- All imports from these modules must be audited.
- Tests must cover connect/disconnect paths.

Risk: Medium — touches the connection runtime path that was recently changed in #1684.

### Slice 3 — Read helper consolidation

Target: merge `read_common.py` into `read_batches.py` or create a `read/` sub-package.

Prerequisites:
- Slice 2 must be stable.
- Read path tests must pass on a real device.

Risk: High — touches the update read cycle. Defer until #1684 real-device validation is done.

### Slice 4 — Mixin review

Target: review whether `capabilities_mixin.py` and `io_mixin.py` should be inlined into
`client.py` or kept as separate concerns.

Prerequisites:
- All previous slices must be stable.
- Only after `check_maintainability.py` reports no violations in `client.py`.

Risk: Low if mechanical, but touches the main client which is central.

---

## 5. Decision Points

Before executing slices, the team must decide:

| Decision | Option A | Option B |
|---|---|---|
| Module size preference | Small focused files (current style) | Topic files (fewer, larger) |
| Sub-package vs single file | `connection/` sub-package | Single `connection.py` |
| Import compatibility | Update all import sites | Brief re-export shim (one PR) |
| Timing | After real-device validation | Before real-device validation |

**Current recommendation:** Follow Option A (small files), use sub-packages for groups with
≥3 files, update import sites directly (no shims), and wait for real-device validation before
any Slice 2+ work.

---

## 6. Validation Checklist (per slice)

Run these after every consolidation slice:

```bash
python -m compileall -q custom_components/thessla_green_modbus tests tools
pytest tests/ -q --tb=long
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
python tools/compare_airpack4_vendor_coverage.py
python tools/compare_registers_with_reference.py --show-renames
python tools/validate_entity_mappings.py
python tools/check_translations.py
python tools/check_maintainability.py
```

All must pass before merging any slice.

---

## 7. Deferred Work

The following are explicitly out of scope until prerequisites are met:

- `read_batches.py` / `read_bits.py` / `read_common.py` consolidation — deferred until
  Slice 2 (connection) is stable and real-device validation is done.
- `connection.py` / `connection_lifecycle.py` / `disconnect.py` merge — deferred until
  real-device validation after #1684 is complete.
- Any consolidation that touches the Modbus read/write runtime.
- Any consolidation that changes public import paths without a full import-site audit.
