# Core Package Consolidation Plan

**Status: Slice 2 merged — runtime_state inlined into client_registers**
**Created: 2026-05-29**
**Updated: 2026-06-01**
**Related PRs: #1685 (planning), #1691 (slice 1 — scanner_kwargs inline), current branch (slice 2)**

---

## 1. Current Layout Inventory

The `core/` package currently has 24 Python files (was 25; `scanner_kwargs.py` inlined into
`client_scanner.py` in slice 1). They are grouped by concern below.

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

### Slice 1 — Tiny internal-only helper ✅ DONE (PR #1691)

**Chosen file:** `scanner_kwargs.py` (35 lines)

**Why:** Grep confirmed only one import site (`core/client_scanner.py`), no external callers,
no test direct-import, no test patch targets. Lowest-risk possible change.

**What was done:**
- `build_scanner_kwargs` function body moved into `core/client_scanner.py`
- `scanner_kwargs.py` deleted (git rm)
- `client_scanner.py` now calls `build_scanner_kwargs` directly (no alias, no shim)
- `test_dependency_direction.py` extended with transport and scanner direction checks
- `docs/core_consolidation_plan.md` updated to reflect completion

**Files moved / deleted:**
| Action | File |
|---|---|
| Deleted | `core/scanner_kwargs.py` |
| Updated (inline target) | `core/client_scanner.py` |

**Import-site changes:**
| File | Old import | New situation |
|---|---|---|
| `core/client_scanner.py` | `from .scanner_kwargs import build_scanner_kwargs as _build_scanner_kwargs_impl` | function defined locally; no import needed |

**Rollback plan:** `git revert <PR #1691 merge commit>`. Re-creates `scanner_kwargs.py` and
restores the import in `client_scanner.py`. Zero runtime effect either way.

**Deferred candidates from original assessment:**

| File | Lines | Reason deferred |
|---|---|---|
| `retry.py` | 269 | Too many external callers (coordinator, core, tests); high blast radius |
| `runtime_state.py` | 25 | One test directly imports it; safe but deferred to slice 2 |

**No behavior changes:** function body of `build_scanner_kwargs` is byte-for-byte identical.

### Slice 2 — Next tiny internal-only helper ✅ DONE (2026-06-01)

**Target:** `runtime_state.py` (25 lines) → inlined into `core/client_registers.py`

**What was done:**
- `mark_registers_failed` and `clear_register_failure` moved into `client_registers.py`
- `runtime_state.py` deleted (git rm)
- `tests/test_coordinator_runtime_state.py` import updated from
  `core.runtime_state` → `core.client_registers`
- Full validation passed

**Files moved / deleted:**
| Action | File |
|---|---|
| Deleted | `core/runtime_state.py` |
| Updated (inline target) | `core/client_registers.py` |
| Updated (test import) | `tests/test_coordinator_runtime_state.py` |

**Rollback plan:** `git revert <B2 commit>`. Re-creates `runtime_state.py`, removes the
inlined functions from `client_registers.py`, and restores the test import. Zero runtime effect.

**core/ file count:** 23 (was 24)

### Slice 3 — Connection helper consolidation

Target: merge `connection_state.py` and `disconnect.py` into `connection_lifecycle.py`
(or into a `connection/` sub-package).

Prerequisites:
- Real-device validation after #1684 must be complete.
- All imports from these modules must be audited.
- Tests must cover connect/disconnect paths.

Risk: Medium — touches the connection runtime path that was recently changed in #1684.

### Slice 4 — Read helper consolidation

Target: merge `read_common.py` into `read_batches.py` or create a `read/` sub-package.

Prerequisites:
- Slice 3 must be stable.
- Read path tests must pass on a real device.

Risk: High — touches the update read cycle. Defer until #1684 real-device validation is done.

### Slice 5 — Mixin review

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

---

## 2026-06-01 B3 Precheck — connection/ sub-package consolidation

**Slice: B3 — DEFERRED**

Precheck rule: "if any connection file was touched in the last 3 PRs, defer."

### Precheck result

`git log --oneline -3` on `main` at time of this batch shows the A1-finish commit in this
very branch modified `core/connection_lifecycle.py`. Additionally, PR #1688 in the merge
history also touched connection files. The precheck fails — B3 is deferred.

### What would have been done

Merge `connection_lifecycle.py`, `disconnect.py`, and `connection_state.py` into a
`core/connection/` sub-package (or into `connection_lifecycle.py`) per Slice 2 plan above.

### Re-evaluation criteria

Re-assess B3 after:
1. This branch is merged and passes real-device validation.
2. No connection-path file is touched in the 3 PRs immediately preceding the B3 attempt.

---

## 2026-06-01 B4 — Read cluster consolidation

**Slice: B4 — BLOCKED**

Blocked: real-device validation for the read path has not yet reached PASS status.

`read_batches.py`, `read_bits.py`, `read_common.py`, `runtime_io.py` will not be moved
or merged until a full real-device read cycle is confirmed correct.

Re-evaluate after the device validation milestone is marked PASS in the project tracker.

---

## 2026-07-08 Slice 3 readiness re-assessment — connection helper consolidation

**Slice: 3 — STILL BLOCKED (on real-device validation only)**

Re-assessed after PR #1745 (targeted read-back allow-list) merged. This note records the
current readiness so the next attempt does not have to re-derive it. **No connection code
was changed in this note.**

### Preconditions status

| Precondition | Status |
|---|---|
| Import/call-site audit complete | ✅ Done — see below |
| Connect/disconnect/lifecycle tests present | ✅ `test_coordinator_connection.py`, `test_coordinator_connection_helpers.py`, `test_coordinator_connection_state.py`, `test_coordinator_disconnect.py`, `test_coordinator_lifecycle.py`, `test_modbus_transport_lifecycle.py` |
| No connection-path file touched in last 3 PRs | ✅ Now satisfied — last change to the three files was `8a399a1` (A1-finish, PR #1674 era); PRs #1741–#1745 did **not** touch them |
| Real-device validation after #1684 complete/PASS | ❌ **NOT met** — `docs/real_device_validation.md` is `PARTIAL`; the IO-ownership (#1684/#1688) row is partial evidence, and the doc states it "must not be marked PASS until all evidence in section 4 is provided" |

**Conclusion:** the only remaining blocker is the real-device-validation gate (plan §7 +
Slice 3 prerequisites + CLAUDE.md §8 "never force a slice whose preconditions are unmet").
The stale B3 precheck reason ("connection files touched in last 3 PRs") no longer applies.

### Import/call-site audit (2026-07-08)

The three target files total 127 lines and are imported by **exactly one** caller,
`core/client_connection.py`:

- `connection_state.py` (24 lines) — `mark_connection_established/_failure/_disconnected`
- `disconnect.py` (50 lines) — `close_client_connection`, `disconnect_locked`
- `connection_lifecycle.py` (53 lines) — `ensure_connected_lifecycle`

Other apparent matches are unrelated: `core/connection.py` and `coordinator/coordinator.py`
only receive these as `*_fn` **callbacks** (parameter names), and `coordinator/state.py` /
`scanner/state.py` define their own similarly-named helpers. No test imports the three
target modules directly (tests exercise them via the coordinator/device-client surface).

### Smallest safe move (when the real-device gate clears)

Per Slice 3 target and CLAUDE.md's "consolidate into the sole caller only when the plan
allows" rule:

1. `git mv`-style inline of `connection_state.py` + `disconnect.py` **into**
   `connection_lifecycle.py` (3 connection-helper files → 1), keeping byte-identical
   function bodies (no logic change).
2. Update the three import blocks in `core/client_connection.py` to import all connection
   lifecycle/state/disconnect symbols from `connection_lifecycle`. No re-export shims.
3. `compileall` after the move to confirm no circular import; run the full per-slice
   validation checklist (§6) including the connection/lifecycle/disconnect tests.
4. Update this plan doc marking Slice 3 DONE with a rollback plan.

**Rollback plan (for the eventual slice):** `git revert` the slice commit — re-creates
`connection_state.py`/`disconnect.py` and restores the imports in `client_connection.py`;
zero runtime effect either way (pure move).

### Re-evaluation criteria

Attempt Slice 3 once `docs/real_device_validation.md` reaches **PASS** (or the maintainer
explicitly waives the real-device gate for this zero-behavior-change move).
