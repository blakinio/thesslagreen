# Home Assistant Quality Scale Audit

**Audit date:** 2026-08-11  
**Current released version:** `2.8.3`  
**Integration:** `thessla_green_modbus`  
**Canonical current status:** [`docs/quality/STATUS.md`](quality/STATUS.md)

This document replaces the May 2026 `2.8.0`/`dev` snapshot. Historical CI counts and branch-specific claims from that snapshot are no longer current.

## Current declaration

`manifest.json` declares `quality_scale: bronze`. This audit does not claim a higher tier than the repository currently declares.

The integration is a local-polling HACS custom integration for ThesslaGreen AirPack units over Modbus TCP, raw RTU-over-TCP, and Modbus RTU/serial transports.

## Verified automated evidence

The 2026-08-10 hardening sequence is complete. PR #1762 merged the primary hardening work and PR #1763 merged the final follow-up. The durable follow-up checkpoint was finalized on `main` as `62e3cb10894767671c7aeb33a5e62b24c82c07ff`.

The GitHub Actions run for `main@62e3cb1` completed all nine current checks successfully. It verifies:

- Ruff/import-order/format and Python compilation;
- vendor register comparison and AirPack 4 coverage;
- translations and maintainability;
- durable checkpoint validation;
- blocking `mypy` validation;
- Hassfest and HACS validation;
- entity mapping validation;
- full pytest on Home Assistant `2026.2.3`;
- focused API contracts on minimum Home Assistant `2026.1.0`;
- focused API contracts on current Home Assistant `2026.8.1` / Python `3.14`;
- `pymodbus` compatibility suites for `3.6.1` and `3.14.0`.

The full suite reports **90.78%** total coverage against an 80% repository minimum.

## Quality-scale-oriented assessment

### Bronze

**Status: supported by repository evidence.**

Key evidence includes config flow, unique config entries, runtime data, entity unique IDs, integration-wide service registration from `async_setup()`, config-entry unloading, polling ownership through the coordinator/device client, and automated config-flow coverage.

Service action schemas do not depend on a loaded config entry. `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)` makes explicit that `async_setup()` exists for process-lifetime service registration while YAML configuration is not supported.

### Silver-oriented requirements

**Status: not fully satisfied by current evidence.**

The current Home Assistant Quality Scale `test-coverage` rule at Silver requires above 95% test coverage for **all integration modules**. The repository's current 90.78% aggregate coverage and several modules below 95% mean that rule is not met today, regardless of the repository's lower 80% CI threshold.

Other Silver-oriented evidence is strong: config-entry unload support, translated/re-raised action failures (`HomeAssistantError` / `ServiceValidationError`), unavailable-state/error handling, reauthentication/reconfiguration support, explicit parallel-update limits, and local polling/reconnect test coverage.

A Silver declaration should only be considered after the complete current checklist is audited and every unmet rule, especially per-module test coverage, is closed.

### Gold-oriented requirements

**Status: partial.**

Implemented pieces include diagnostics with redaction, translated entities, device information plumbing, entity categories, disabled-by-default diagnostics/risky configuration entities, documented limitations, and Repairs support for actionable final Modbus write failures.

The principal unproven area is physical-device validation across the supported transport/model matrix. Existing AirPack 4 evidence predates the 2026-08-10 hardening changes.

### Platinum-oriented requirements

**Status: not claimed.**

Strict typing is a blocking CI gate, but a Platinum claim requires an intentional audit of every current Platinum rule, not only successful mypy execution.

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

GitHub CI cannot prove physical Modbus behavior. The following remain explicit external acceptance checks against the actual post-hardening candidate:

- AirPack post-hardening smoke test;
- RTU/USB validation using a stable `/dev/serial/by-id/...` path;
- network-loss/reconnect behavior;
- representative safe writes with read-back;
- 24–72 hour polling soak.

See [`docs/real_device_validation.md`](real_device_validation.md).

## Architecture decision

Further broad read-path or mixin consolidation is intentionally deferred. [`docs/core_consolidation_plan.md`](core_consolidation_plan.md) requires real-device validation before additional high-risk restructuring. The current modularity is therefore not treated as an automatic defect to be refactored without hardware evidence.
