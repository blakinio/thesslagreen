# Refactor & Large-Change Guidelines

## PR checklist (large methods/files/refactors)

Use this checklist when a PR changes a large module/method or introduces cross-layer behavior changes.

- [ ] **Extraction rationale**: why the split improves readability/maintenance.
- [ ] **Behavior compatibility**: list public APIs/facades kept compatible.
- [ ] **Error contract impact**: confirm retry/error classification remains consistent across transport/coordinator/scanner.
- [ ] **Test impact**: list tests added/updated (including contract tests for cross-layer behavior when relevant).
- [ ] **Rollback plan**: brief note how to revert safely if regressions appear.

## When to extract a function

Extract when at least one is true:

1. Method mixes more than one concern (e.g. parsing + state mutation + logging + retry).
2. Branching/nesting obscures the happy-path.
3. Same logic appears in more than one module/layer.
4. Function exceeds maintainability thresholds or is close to them.

## When to split a module

Split when:

1. Module becomes a catch-all for unrelated responsibilities.
2. Runtime contract becomes hard to test in isolation.
3. Import-time coupling blocks local unit tests.

Prefer thin compatibility facades/re-exports when splitting public entry points.

## When to add a cross-layer contract test

Add/adjust contract tests when changing:

- retry policy,
- error classification/propagation,
- transport fallback behavior,
- shared logging semantics for attempts/backoff/reason.

At minimum, verify transport/coordinator/scanner classify the same exception type to the same `(kind, reason)` contract.
