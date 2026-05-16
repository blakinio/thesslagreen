# Final Transport Shim Inventory

Branch: `claude/remove-final-shim-Kn2oC`
Base: `main`

## Shim Under Review

`custom_components/thessla_green_modbus/modbus_transport.py`

## Finding: Shim Already Removed

The file `modbus_transport.py` was removed in a prior commit
(`ed88bb3c` — "fix: repair broken transport imports and remove modbus_transport shim"),
which predates this branch. It does not exist on `main`.

There is no shim file to delete. This pass focuses on removing stale references
left over from when the file existed.

## Prior Shim Contents (from git history)

The shim was a pure re-export module that forwarded names from
`transport.retry` and `transport.retry_logging` into the root namespace.
It contained no real logic — only `from .transport.retry import ...` and
`from .transport.retry_logging import ...` statements.

## Remaining Stale References (before this pass)

| Location | Kind | Detail |
|----------|------|--------|
| `tools/check_maintainability.py:17` | Dead config entry | `STRICT_PATH_LIMITS` contained an entry for the now-deleted path; the entry was never matched at runtime but was misleading |
| `tests/test_error_contract.py:69` | Stale logger name string | `logging.getLogger("...modbus_transport")` used as an arbitrary logger name in a cross-layer retry-logging test; the test does not import from the deleted module, but the name referenced the old shim path |
| `docs/final_architecture_cleanup.md:14` | Outdated doc claim | Stated "modbus_transport.py remains as a minimal shim"; this was written before the shim was deleted |

## Canonical Replacement Module Paths

All symbols formerly re-exported by `modbus_transport.py` are now in:

| Symbol | Canonical module |
|--------|-----------------|
| `calculate_backoff` | `transport.retry` |
| `classify_transport_error` | `transport.retry` |
| `should_retry` | `transport.retry` |
| `ErrorKind` | `transport.retry` |
| `RetryDecision` | `transport.retry` |
| `log_transport_retry` | `transport.retry_logging` |
| `apply_transport_backoff` | `transport.retry_logging` |

## Classification of Usage

| Reference | Type | Safely removable / fixable? |
|-----------|------|-----------------------------|
| `tools/check_maintainability.py` STRICT_PATH_LIMITS entry | Tooling dead code | Yes — remove the stale dict entry |
| `tests/test_error_contract.py` logger name string | Test string (not an import) | Yes — update string to canonical module path |
| `docs/final_architecture_cleanup.md` claim | Documentation (outdated) | Yes — update to reflect removal |

## Verdict

The shim is safely fully removed. No active production imports, no active test
imports from `modbus_transport` exist. Only three stale references (one tool
config entry, one logger-name string, one doc sentence) remain and are fixed by
this pass.
