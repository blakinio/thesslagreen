# Home Assistant Quality Scale Audit

**Audit date:** 2026-08-10  
**Current released version:** `2.8.3`  
**Integration:** `thessla_green_modbus`  
**Canonical current status:** [`docs/quality/STATUS.md`](quality/STATUS.md)

This document replaces the May 2026 `2.8.0`/`dev` snapshot. Historical CI counts and branch-specific claims from that snapshot are no longer current.

## Current declaration

`manifest.json` declares `quality_scale: bronze`. This audit does not claim a higher tier than the repository currently declares.

The integration is a local-polling HACS custom integration for ThesslaGreen AirPack units over Modbus TCP, raw RTU-over-TCP, and Modbus RTU/serial transports.

## Verified automated evidence

PR #1762 merged to `main` as `088677385a179a0a02c14ddae3dd96d20c2534e0` after canonical CI #1146 completed successfully. That run verified:

- Ruff and import-order checks;
- Ruff formatting;
- Python compilation;
- vendor register comparison and AirPack 4 coverage;
- translations;
- repository maintainability gate;
- durable agent checkpoint validation;
- Hassfest;
- HACS validation;
- entity mapping validation;
- full pytest suite with 90.68% coverage against an 80% minimum.

The follow-up hardening task adds mandatory mypy, declared-minimum Home Assistant API tests, immutable GitHub Action refs, repair-issue lifecycle, and cleanup of stale process-memory energy state. Those items are only marked verified after the follow-up PR's final CI run is green.

## Quality-scale-oriented assessment

### Bronze

**Status: supported by repository evidence.**

Key evidence includes config flow, unique config entries, runtime data, entity unique IDs, integration-wide service registration from `async_setup()`, config-entry unloading, polling ownership through the coordinator/device client, and automated config-flow coverage.

After PR #1762, service action schemas no longer depend on a loaded config entry. The follow-up also declares `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)` because `async_setup()` exists only for process-lifetime service registration and YAML configuration is not supported.

### Silver-oriented requirements

**Status: substantially implemented, but not declared as the repository tier.**

Evidence includes:

- config-entry unload support;
- translated/re-raised action failures (`HomeAssistantError` / `ServiceValidationError`);
- unavailable-state/error handling;
- reauthentication/reconfiguration support;
- parallel-update limits;
- test coverage above the repository threshold;
- local polling and reconnect behavior covered by automated tests.

A higher declared tier should only be considered after the owner intentionally reviews the complete current Home Assistant Quality Scale checklist against this custom integration.

### Gold-oriented requirements

**Status: partial.**

Implemented pieces include diagnostics with redaction, translated entities, device information, entity categories, disabled-by-default diagnostics/risky configuration entities, documented limitations, and Repairs support for actionable final Modbus write failures.

The principal unproven area is physical-device validation across the supported transport/model matrix. Existing AirPack 4 evidence predates the 2026-08-10 hardening changes.

### Platinum-oriented requirements

**Status: not claimed.**

The follow-up adds strict typing as a blocking CI gate, but a Platinum claim would require an intentional audit of every current Platinum rule, not only successful mypy execution.

## Safety-sensitive implementation notes

### Modbus writes

All Home Assistant-facing write paths must fail explicitly when the device rejects or cannot complete a write. A logged Modbus exception must never be converted into a successful Home Assistant action.

Final transport/write failures create an actionable Repairs issue scoped to the affected config entry. A later confirmed write clears that issue.

### Diagnostic full scan

`scan_all_registers` is an advanced diagnostic operation. It serializes normal coordinator I/O, disconnects the primary transport, performs the scan using the configured transport semantics, and restores the primary connection before releasing the I/O lock. It should not be treated as a routine automation action.

`validate_known_registers` remains the preferred normal validation path.

### Derived electrical metrics

`electrical_power` is an instantaneous **estimate**, not a metered value. The previous process-memory `total_energy` accumulator and stale `estimated_power` alias were removed because they reset with the integration process and therefore were not suitable for durable Home Assistant energy semantics.

## External validation boundary

GitHub CI cannot prove physical Modbus behavior. The following remain explicit external acceptance checks:

- AirPack post-hardening smoke test;
- RTU/USB validation using a stable `/dev/serial/by-id/...` path;
- network-loss/reconnect behavior;
- representative safe writes with read-back;
- 24–72 hour polling soak.

See [`docs/real_device_validation.md`](real_device_validation.md).

## Architecture decision

Further broad read-path or mixin consolidation is intentionally deferred. [`docs/core_consolidation_plan.md`](core_consolidation_plan.md) requires real-device validation before additional high-risk restructuring. The current modularity is therefore not treated as an automatic defect to be refactored without hardware evidence.
