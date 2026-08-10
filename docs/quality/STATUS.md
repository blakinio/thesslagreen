# ThesslaGreen Modbus quality status

**Status date:** 2026-08-10  
**Current released version:** `2.8.3`  
**Repository quality declaration:** Home Assistant `bronze`  
**Minimum Home Assistant:** `2026.1.0`  
**Runtime Modbus dependency:** `pymodbus>=3.6.0,<4.0`

This file is the canonical snapshot for current quality, validation, and release-readiness status. Historical audit documents may describe older commits and must not be interpreted as the current state unless explicitly marked current.

## Automated verification

The hardening change merged as PR #1762 (`088677385a179a0a02c14ddae3dd96d20c2534e0`). Its final canonical CI run #1146 passed all repository jobs: lint/format, compilation, vendor register coverage, translations, maintainability, checkpoint validation, Hassfest, HACS, entity mappings, and the full pytest suite. The full suite reported 90.68% coverage against the repository's 80% minimum.

The follow-up hardening task adds:

- mandatory `mypy` validation using the repository's strict typing configuration;
- a focused compatibility gate against the declared minimum Home Assistant `2026.1.0`;
- commit-SHA pinning for third-party GitHub Actions used by CI and release workflows;
- an explicit config-entry-only schema for the process-level `async_setup()` hook;
- runtime Repairs issue lifecycle for final Modbus write failures;
- removal of volatile in-memory `total_energy` accumulation and stale `estimated_power` aliases.

These follow-up items are considered complete only after the follow-up PR's final CI run is green.

## Real-device evidence

Real-device evidence is **partial**, not complete. Existing evidence covers an AirPack 4 over Modbus TCP and predates the 2026-08-10 hardening changes. It remains useful historical evidence but does not prove post-hardening behavior.

Required external acceptance still includes:

- post-hardening TCP smoke test on a physical AirPack;
- RTU/USB validation using a stable `/dev/serial/by-id/...` path;
- reconnect/network-loss behavior;
- safe write/read-back verification;
- 24–72 hour polling soak with no transport desynchronization.

GitHub CI cannot prove these hardware conditions. They must stay explicitly `PENDING` until measured on a real unit.

## Deliberately deferred work

Broad read-path/mixin/module consolidation is deliberately deferred. `docs/core_consolidation_plan.md` requires longer real-device validation before further high-risk runtime restructuring. This is a safety decision, not unfinished accidental scope.

## Release status

`v2.8.3` is the current published GitHub release. The hardening work merged after that release and therefore belongs to a future version/release; no new release tag should be created until the repository owner intentionally selects the next version and the real-device acceptance level required for that release.
