# Core Package Consolidation Plan

**Status: Slices 1–3 + narrow Slice 4 complete, plus final polish — `core/` has 19 files (excl. `__init__.py`)**
**Created: 2026-05-29**
**Updated: 2026-07-09**
**Related PRs: #1685 (planning), #1691 (Slice 1 — scanner_kwargs inline), Slice 2 — runtime_state inline, #1748 (Slice 3 — connection helper consolidation), #1750 (Slice 4 narrow — read_common → read_batches), #1752 (final polish)**

> **Current recommendation (2026-07-09):** the safe consolidation slices are done.
> **Do not start any further runtime refactor before longer real-device validation.**
> The next safe work is real-device validation evidence and release prep — not more
> file moves. Keep `core/client.py` as the mixin assembler, and keep `quality_scale`
> at `bronze` until `docs/real_device_validation.md` reaches PASS. The remaining
> candidates (broad Slice 4 `read/` package, Slice 5 mixin review, merging mixins
> into `client.py`) are **DEFERRED / NOT RECOMMENDED NOW** — see §4 and §7.

---

## 1. Current Layout Inventory

The `core/` package currently has **19 Python files** (excluding `__init__.py`). Five
modules from the original inventory have been inlined into their callers across Slices
1–4 and are no longer present: `scanner_kwargs.py`, `runtime_state.py`,
`connection_state.py`, `disconnect.py`, `read_common.py`. Files are grouped by concern
below; this matches `docs/architecture/file_inventory.md` (canonical current structure).

### 1.1 Main client entry point

| File | Concern |
|---|---|
| `client.py` | `ThesslaGreenDeviceClient` — assembles all mixins into the main device client |

### 1.2 Connection concern

| File | Concern |
|---|---|
| `connection.py` | High-level connection helpers shared by client and scanner |
| `connection_lifecycle.py` | Async connection open/close **plus** connection-state tracking and disconnect/teardown helpers (former `connection_state.py` + `disconnect.py`, inlined in Slice 3) |
| `connection_test.py` | Register-probe helpers for connection validation |
| `transport_select.py` | Transport selection logic (TCP vs RTU, mode detection) |
| `client_connection.py` | `_DeviceClientConnectionMixin` — connection lifecycle mixin |

### 1.3 Read path concern

| File | Concern |
|---|---|
| `read_batches.py` | Batched multi-register reads **plus** shared low-level read retry/error helpers (former `read_common.py`, inlined in narrow Slice 4) |
| `read_bits.py` | Coil / discrete input reads |
| `runtime_io.py` | High-level runtime read/write dispatcher |
| `io_mixin.py` | `_ModbusIOMixin` — Modbus read protocol mixin used by DeviceClient |
| `client_registers.py` | `_DeviceClientRegistersMixin` — register IO helpers mixin (also holds the former `runtime_state.py` failure-tracking helpers, inlined in Slice 2) |

### 1.4 Write path concern

| File | Concern |
|---|---|
| `write_path.py` | `SingleWritePlan`, `encode_write_value` (write operations, user units → raw) |

### 1.5 Scanner support

| File | Concern |
|---|---|
| `client_scanner.py` | `_DeviceClientScannerMixin` — scanner orchestration methods (also holds the former `scanner_kwargs.py` `build_scanner_kwargs`, inlined in Slice 1) |
| `scan_helpers.py` | Scan result processing helpers |

### 1.6 Capability / model / register helpers

| File | Concern |
|---|---|
| `capabilities_mixin.py` | `_CoordinatorCapabilitiesMixin` — derived capability metrics |
| `models.py` | `CoordinatorConfig` and related data models |
| `register_groups.py` | Register group grouping and iteration helpers |
| `register_processing.py` | Register value post-processing (scaling, enum decode, etc.) |

### 1.7 Retry helper

| File | Concern |
|---|---|
| `retry.py` | Retry/backoff utilities |

---

## 2. Recommended Target Layout

The original long-term target proposed `connection/` and `read/` sub-packages. The
connection concern has since been consolidated **in place** (three files → one
`connection_lifecycle.py`) rather than into a sub-package, which was simpler and
lower-risk. The `read/` sub-package is **DEFERRED / NOT RECOMMENDED NOW** — see the
note below.

```text
core/
  __init__.py
  client.py              # ThesslaGreenDeviceClient (unchanged — assembles mixins)
  models.py              # CoordinatorConfig, data models (unchanged)
  connection.py          # high-level connection helpers (unchanged)
  connection_lifecycle.py# open/close + state + disconnect (Slice 3 consolidated these)
  connection_test.py     # connection probe (unchanged)
  transport_select.py    # transport selection (unchanged)
  client_connection.py   # _DeviceClientConnectionMixin (unchanged)
  read_batches.py        # batched reads + shared read helpers (narrow Slice 4)
  read_bits.py           # coil/discrete reads (unchanged — DEFERRED from broad Slice 4)
  runtime_io.py          # runtime read/write dispatcher (unchanged — DEFERRED)
  io_mixin.py            # _ModbusIOMixin (unchanged — DEFERRED)
  client_registers.py    # _DeviceClientRegistersMixin (unchanged)
  write_path.py          # write operations (unchanged)
  client_scanner.py      # _DeviceClientScannerMixin (unchanged)
  scan_helpers.py        # unchanged
  capabilities_mixin.py  # unchanged
  register_groups.py     # unchanged
  register_processing.py # unchanged
  retry.py               # unchanged
```

### Notes on target layout

- **Do not merge `client.py` into a monolith** — keep it as the assembler of mixins.
- The `connection/` sub-package was **not** created; in-place consolidation into
  `connection_lifecycle.py` achieved the same file-count reduction with less churn.
- A `read/` sub-package (moving `read_bits.py` / `runtime_io.py` / `io_mixin.py` into
  `core/read/`) is **DEFERRED / NOT RECOMMENDED NOW** — it touches the live read/update
  cycle and must wait for real-device read-path validation = PASS.
- Circular imports are the primary risk; always verify with `python -m compileall`
  after any future move.

---

## 3. Consolidation Rules

These rules apply to every consolidation slice:

1. **Preserve public imports** — update all import sites directly. No re-export shims
   (per `docs/thesslagreen_guidelines.md`, compatibility shims are forbidden).

2. **No behavior changes** — consolidation is file moves only. No logic changes.

3. **Use `git mv`** — preserves history. Never copy-paste.

4. **One concern per PR** — do not mix connection and read consolidation in the same PR.

5. **Run full validation after every slice** — see the validation checklist (§6).

6. **Avoid actively-touched files** — if a file was modified in the last 3 PRs or is
   referenced in a real-device fix, defer its consolidation.

7. **Respect the real-device gate** — never force a slice whose preconditions
   (real-device validation PASS, a prior slice being stable) are unmet.

---

## 4. Slice status

### Slice 1 — Tiny internal-only helper ✅ DONE (PR #1691)

`scanner_kwargs.py` (35 lines) inlined into `core/client_scanner.py`; module deleted.
No external callers, no shims. See the dated log below for the full record.

### Slice 2 — Next tiny internal-only helper ✅ DONE (2026-06-01)

`runtime_state.py` (25 lines) inlined into `core/client_registers.py`; module deleted.
One test import updated. See the dated log below.

### Slice 3 — Connection helper consolidation ✅ DONE (PR #1748)

`connection_state.py` and `disconnect.py` inlined into `connection_lifecycle.py`
(three connection-helper files → one); both modules deleted. `client_connection.py`
and two tests updated to import from `connection_lifecycle`. Maintainer explicitly
waived the real-device gate for this zero-behavior-change move. See the dated log below.

### Slice 4 — Read helper consolidation

- **Narrow step ✅ DONE (PR #1750):** `read_common.py` (6 shared low-level read
  helpers) inlined into `read_batches.py`; module deleted. `io_mixin.py` and
  `tests/test_read_common.py` updated. Maintainer-waived pure move. See the dated log.
- **Broad step ❌ DEFERRED / NOT RECOMMENDED NOW:** moving `read_bits.py` /
  `runtime_io.py` / `io_mixin.py` into a `core/read/` sub-package. This touches the
  live read/update cycle and is **BLOCKED** on real-device read-path validation = PASS.

### Slice 5 — Mixin review ❌ DEFERRED / NOT RECOMMENDED NOW

Reviewing whether `capabilities_mixin.py` and `io_mixin.py` should be inlined into
`client.py` is **not recommended now**. Merging any mixin into `client.py` is
explicitly out of scope until longer real-device validation is complete — and
`client.py` must remain the mixin assembler regardless (CLAUDE.md hard rule).

### Final polish ✅ DONE (PR #1752)

Not a consolidation slice, but the closing cleanup of the refactor series: removal of
no-caller wrappers/constants (two private `_ModbusIOMixin` static-method wrappers and
three unreferenced `const.py` constants), scanner test-helper consolidation into
`tests/helpers_scanner.py`, a docs consistency audit, and removal of the orphaned
`.bandit` config. No runtime behavior, register, entity/service ID, or translation
changes. See `CHANGELOG.md` and PR #1752.

---

## 5. Decision Points & current recommendation

| Decision | Chosen |
|---|---|
| Module size preference | Small focused files (current style) |
| Sub-package vs single file | In-place inline (no sub-packages created so far) |
| Import compatibility | Update all import sites directly (no shims) |
| Timing of remaining slices | **After** longer real-device validation only |

**Current recommendation (2026-07-09):**

- **No further runtime refactor before longer real-device validation.** The remaining
  candidates all touch the live read path or the central client and carry real
  regression risk without new real-device evidence.
- **Next safe work is real-device validation evidence and release prep**, not more
  file moves. See `docs/real_device_validation.md` and `docs/release_readiness.md`.
- **Keep `core/client.py` as the mixin assembler** — do not merge mixins into it.
- **Keep `quality_scale` at `bronze`** until `docs/real_device_validation.md` is
  marked PASS with committed real-device evidence.

---

## 6. Validation Checklist (per slice)

Run these after any consolidation slice (and for the release/validation work that
follows). If `pytest` cannot collect in the local sandbox (Python < 3.13), run the
rest and flag that full `pytest` needs CI verification on Python 3.13.

```bash
python -m compileall -q custom_components/thessla_green_modbus tests tools
pytest --collect-only -q
pytest tests/ -q --tb=long
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
python tools/compare_registers_with_reference.py --show-renames
python tools/compare_airpack4_vendor_coverage.py
python tools/check_maintainability.py
python tools/validate_entity_mappings.py
python tools/check_translations.py
python tools/validate_registers.py
```

All applicable commands must pass before merging any slice.

---

## 7. Deferred Work

The following are explicitly out of scope until their prerequisites (chiefly
real-device validation = PASS) are met:

- **Broad Slice 4** — moving `read_bits.py` / `runtime_io.py` / `io_mixin.py` into a
  `core/read/` sub-package. **DEFERRED / NOT RECOMMENDED NOW** — touches the live
  read/update cycle.
- **Slice 5 mixin review** — inlining `capabilities_mixin.py` / `io_mixin.py`.
  **DEFERRED / NOT RECOMMENDED NOW.**
- **Merging any mixin into `client.py`.** **NOT RECOMMENDED** — `client.py` must stay
  the mixin assembler (CLAUDE.md hard rule).
- Any consolidation that touches the Modbus read/write runtime.
- Any consolidation that changes public import paths without a full import-site audit.

**Only real-device validation evidence remains before considering further runtime
refactors.** No broad read-path refactor, no Slice 5 mixin review, and no merging of
mixins into `client.py` should be attempted before that validation is complete.

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

**Slice: B4 — SUPERSEDED** (see "2026-07-08 Slice 4 — DONE" below)

Originally blocked: real-device validation for the read path had not reached PASS status.
The narrow Slice 4 step (`read_common.py` → `read_batches.py`) was executed on 2026-07-08
as a maintainer-waived pure move; `read_bits.py` and `runtime_io.py` were **not** touched
and remain deferred until a full real-device read cycle is confirmed correct.

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

---

## 2026-07-08 Slice 3 — DONE (connection helper consolidation)

**Slice: 3 — ✅ DONE** (maintainer explicitly waived the real-device gate for this
zero-behavior-change move; all other preconditions were met per the readiness re-assessment
above).

### What was done

- `connection_state.py` (3 helpers) and `disconnect.py` (2 helpers) were **inlined into
  `connection_lifecycle.py`** with byte-identical function bodies (imports merged). The
  three connection-helper files became one; `core/` file count 23 → 21.
- `connection_state.py` and `disconnect.py` were **deleted** (`git rm`).
- The sole caller `core/client_connection.py` now imports `mark_connection_established`,
  `mark_connection_failure`, `mark_connection_disconnected`, `close_client_connection`,
  `disconnect_locked`, and `ensure_connected_lifecycle` all from `connection_lifecycle`.
  No re-export shims.

### Correction to the readiness note above

The readiness re-assessment stated "No test imports the three target modules directly."
That was **inaccurate** — two tests imported them and were updated directly (no shims):

| File | Old import | New import |
|---|---|---|
| `tests/test_coordinator_connection_state.py` | `from core.connection_state import …` | `from core.connection_lifecycle import …` |
| `tests/test_coordinator_disconnect.py` | `from core import disconnect` (`disconnect.disconnect_locked`, `disconnect.close_client_connection`) | `from core import connection_lifecycle` (`connection_lifecycle.…`) |

Test file names were left unchanged (they still describe the behaviour they cover).
`docs/architecture/file_inventory.md` was updated to drop `disconnect.py`.

### Files moved / deleted

| Action | File |
|---|---|
| Deleted | `core/connection_state.py` |
| Deleted | `core/disconnect.py` |
| Updated (inline target) | `core/connection_lifecycle.py` |
| Updated (imports) | `core/client_connection.py` |
| Updated (test imports) | `tests/test_coordinator_connection_state.py`, `tests/test_coordinator_disconnect.py` |
| Updated (docs) | `docs/architecture/file_inventory.md` |

### Validation

`compileall`, `ruff`/`ruff -I`/`ruff format --check`, `check_maintainability`,
`validate_entity_mappings`, `check_translations`, `validate_registers`, and the register
comparison tools all pass. `connection_lifecycle` imports standalone and `client_connection`
resolves all six impl aliases from it (no circular import). Full `pytest` (incl.
`test_coordinator_connection*.py`, `test_coordinator_disconnect.py`,
`test_coordinator_lifecycle.py`, `test_modbus_transport_lifecycle.py`) runs on CI (Python
3.13); the local sandbox is 3.11.

### Rollback plan

`git revert` the slice commit — re-creates `connection_state.py`/`disconnect.py`, removes
the inlined functions from `connection_lifecycle.py`, and restores the imports in
`client_connection.py` and the two tests. Zero runtime effect either way (pure move).

### Follow-ups

- Slice 4 (read helper consolidation) — the narrow `read_common.py` → `read_batches.py`
  step was subsequently executed (maintainer-waived); see "2026-07-08 Slice 4 — DONE".

---

## 2026-07-08 Slice 4 — DONE (narrow read helper consolidation)

**Slice: 4 (narrow) — ✅ DONE** (maintainer explicitly waived the real-device read-path
gate for this zero-behavior-change move). Only the narrow plan option was taken —
`read_common.py` → `read_batches.py`. The broader `read/` sub-package and any move of
`read_bits.py` / `runtime_io.py` / `io_mixin.py` were **not** done and remain deferred
until real-device read-path validation reaches PASS.

### What was done

- `core/read_common.py` (6 shared low-level read helpers: `ILLEGAL_DATA_ADDRESS`,
  `is_illegal_data_address_response`, `is_transient_error_response`, `execute_read_call`,
  `log_read_retry`, `raise_for_error_response`) was **inlined into `core/read_batches.py`**
  with byte-identical function bodies (imports merged). `core/` file count 21 → 20.
- `core/read_common.py` was **deleted** (`git rm`).
- Import sites updated directly (no shims): `core/io_mixin.py` (the sole production
  consumer — 5 `from .read_common import …` → `from .read_batches import …`) and
  `tests/test_read_common.py`.

### Why this was low-risk despite the read-path gate

`read_common.py` and `read_batches.py` are **independent leaves** — neither imports the
other or any other read-cluster module. In production both are consumed **only** by
`core/io_mixin.py` (which is itself imported only by `core/client.py`). Merging two
siblings that share a single consumer introduces no new import edge and no cycle
(verified: `read_batches` imports resolve, `io_mixin` resolves all impl aliases). It is a
pure move with no logic change, so the read/update cycle behaviour is unchanged.

### Files moved / deleted

| Action | File |
|---|---|
| Deleted | `core/read_common.py` |
| Updated (inline target) | `core/read_batches.py` |
| Updated (imports) | `core/io_mixin.py` |
| Updated (test import) | `tests/test_read_common.py` |
| Updated (docs) | `docs/coordinator_proxy_remaining_plan.md` |

### Validation

`compileall`, `ruff`/`ruff -I`/`ruff format --check`, `check_maintainability`,
`validate_entity_mappings`, `check_translations`, `validate_registers`, and the register
comparison tools all pass. `read_batches` exposes all six merged symbols and `io_mixin`
resolves all five impl aliases (no circular import). Full `pytest` (incl.
`test_read_common.py`, `test_read_batches.py`, `test_io_mixin*`) runs on CI (Python 3.13);
the local sandbox is 3.11.

### Rollback plan

`git revert` the slice commit — re-creates `read_common.py`, removes the inlined helpers
from `read_batches.py`, and restores the imports in `io_mixin.py` and the test. Zero
runtime effect either way (pure move).

### Still deferred

- `read_bits.py`, `runtime_io.py`, `io_mixin.py` consolidation and any `read/` sub-package
  remain **BLOCKED** on real-device read-path validation = PASS.

---

## 2026-07-09 Docs refresh — plan aligned with completed slices

**Docs-only.** Sections 1–7 above were refreshed to reflect the current repository state
after Slices 1–3, narrow Slice 4, and the PR #1752 final polish:

- Header status/date/PR list updated; `core/` file count corrected to **19** (excl.
  `__init__.py`). The stale "Slice 2 merged / 24 files / 2026-06-01" header was removed.
- The Current Layout Inventory (§1) now lists the real 19 files and no longer references
  the deleted `scanner_kwargs.py`, `runtime_state.py`, `connection_state.py`,
  `disconnect.py`, or `read_common.py`. It matches `docs/architecture/file_inventory.md`.
- Completed slices recorded (§4): Slice 1 (scanner_kwargs → client_scanner), Slice 2
  (runtime_state → client_registers), Slice 3 (connection_state + disconnect →
  connection_lifecycle), narrow Slice 4 (read_common → read_batches), and the final polish
  (no-caller wrappers/constants removed, scanner test helpers consolidated).
- Broad Slice 4 (`read/` package move), Slice 5 mixin review, and merging mixins into
  `client.py` marked **DEFERRED / NOT RECOMMENDED NOW** (§2, §4, §7).
- Current recommendation added (§5): no further runtime refactor before longer real-device
  validation; next safe work is validation evidence + release prep; keep `client.py` as the
  mixin assembler; keep `quality_scale` at `bronze` until validation PASS.
- Validation checklist (§6) refreshed to the full current command set.

No runtime, register, entity/service ID, or translation changes. The dated log entries
above are preserved as historical record.
