# Remaining Test Failures After Cleanup (PRs #1625, #1627)

## Phase 1 — Reproduced Failures

### Exact Failing Tests

```
FAILED tests/test_coordinator.py::test_reconfigure_does_not_leak_connections
FAILED tests/test_error_contract.py::test_cross_layer_classification_contract
FAILED tests/test_error_contract.py::test_cross_layer_classification_contract_matrix[exc0-transient-timeout]
FAILED tests/test_error_contract.py::test_cross_layer_classification_contract_matrix[exc1-transient-cancelled]
FAILED tests/test_error_contract.py::test_cross_layer_classification_contract_matrix[exc2-transient-connection]
FAILED tests/test_error_contract.py::test_cross_layer_classification_contract_matrix[exc3-permanent-modbus]
```

6 failures total: 5 × error_contract return-type mismatch, 1 × coordinator await-expression bug.

---

## Failure 1 — error_contract return-type mismatch (5 tests)

### Affected module
`custom_components/thessla_green_modbus/transport/retry.py` — `classify_transport_error`

### Failure message (representative)
```
AssertionError: assert RetryDecision(retry=True, kind=<ErrorKind.TRANSIENT: 'transient'>, reason='timeout') == ('transient', 'timeout')
```

### Root cause
`tests/test_error_contract.py` asserts that all three cross-layer classifiers return the same type:
```python
assert classify_retry_error(exc)    == (expected_kind, expected_reason)  # tuple — OK
assert classify_scanner_error(exc)  == (expected_kind, expected_reason)  # tuple — OK
assert classify_transport_error(exc) == (expected_kind, expected_reason) # RetryDecision — FAIL
```

`classify_retry_error` and `classify_scanner_error` both return `(decision.kind.value, decision.reason)` (a tuple), but `classify_transport_error` returns the full `RetryDecision` dataclass.

### Category
**error_contract return-type mismatch**

---

## Failure 2 — coordinator await-expression bug (1 test)

### Affected module
`custom_components/thessla_green_modbus/coordinator/coordinator.py` — `_build_transport_selector_fn`

### Failure message
```
TypeError: object function can't be used in 'await' expression
  File "coordinator/connection.py:252"
    selected_transport, selected_mode = await ensure_transport_selected_fn()
```

### Traceback snippet
```
custom_components/thessla_green_modbus/coordinator/connection.py:252:
    selected_transport, selected_mode = await ensure_transport_selected_fn()
TypeError: object function can't be used in 'await' expression
```

### Root cause
`_build_transport_selector_fn` returns a sync function `_ensure_transport_selected`, which when called returns another sync lambda `lambda: _ensure_transport_selected_impl(...)`.

In `connection.py` the code does `await ensure_transport_selected_fn()` expecting a coroutine, but the inner function returns a lambda (not a coroutine), so `await` fails.

The fix: make `_ensure_transport_selected` an `async def` that directly `await`s `_ensure_transport_selected_impl(...)` instead of wrapping it in a lambda.

### Category
**coordinator await-expression bug**

---

## Phase 2 — Fix: error_contract return-type mismatch

**Decision**: Keep `classify_transport_error` returning `RetryDecision` (it has callers that access `.retry`, `.kind`, `.reason`). Add tuple-equality support to `RetryDecision` so that `RetryDecision(...) == ("transient", "timeout")` works. This is done by setting `eq=False` on the dataclass and defining a custom `__eq__` that compares `(self.kind.value, self.reason)` against a 2-tuple.

**Files changed**: `custom_components/thessla_green_modbus/transport/retry.py`

---

## Phase 3 — Fix: coordinator await-expression bug

**Fix**: Changed `_ensure_transport_selected` from a sync function returning a lambda to an `async def` that directly `await`s `_ensure_transport_selected_impl(...)`.

**Files changed**: `custom_components/thessla_green_modbus/coordinator/coordinator.py`

---

## Phase 4 — Tests Run

```
pytest -q tests/ -k "error_contract or retry or transport or backoff" --tb=long
pytest -q tests/ -k "coordinator or initialization or setup" --tb=long -vv
pytest tests/ -q --tb=long
```

---

## Remaining Failures

None — full suite green after fixes.

---

## Deferred Work

- Coordinator DeviceClient redesign: **deferred** — not included in this PR.
- No dependency bump included in this PR (pydantic 2.13.4 was already on main from PR #1625).
- No entity IDs changed.
- No unique IDs changed.
- No service IDs changed.
- No register names or addresses changed.
- No Modbus behavior changed.
