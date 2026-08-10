# Home Assistant integration hardening — 2026-08-10

Status: implementation under CI validation

## Scope

This hardening pass follows a repository-wide static audit of the Home Assistant boundary, Modbus write semantics, diagnostic scanning, risky entity exposure, dependency metadata, and CI contracts.

## Verified findings on the pre-change `main`

1. Service target extraction called Home Assistant's asynchronous `async_extract_entity_ids()` without awaiting it and discarded the coroutine, so indirect targets such as devices, areas, floors, labels, and groups could be silently ignored.
2. Integration services were registered from `async_setup_entry()` and removed based on config-entry count instead of being process-lifetime registrations from `async_setup()`.
3. Several service write paths converted Modbus failures or `False` results into log messages while the Home Assistant action still completed successfully.
4. Targeted service schemas required a raw `entity_id`, preventing standard Home Assistant device/area/floor/label targeting at schema validation time.
5. `scan_all_registers` opened a second Modbus connection while coordinator polling remained active.
6. Known-register validation could classify transport failures as unsupported/missing registers.
7. Mapping risk metadata was diagnostic only; dangerous communication/security/reset controls were enabled by default.
8. Package version/dependency metadata was inconsistent (`manifest.json` 2.8.3 vs `pyproject.toml` 2.8.0; runtime requirements lacked the manifest's `<4.0` pymodbus boundary).

## Implemented design decisions

- Standard Home Assistant target resolution is asynchronous and uses the framework extractor.
- Targeted service schemas use `cv.make_entity_service_schema`.
- Integration-wide actions are registered once from `async_setup()` and are not removed when one config entry unloads.
- Device/action failures are surfaced as `HomeAssistantError`; invalid targets/unsupported requested operations use `ServiceValidationError`.
- Full diagnostic scans acquire the DeviceClient I/O lock, disconnect the primary transport, scan with the same configured transport type/settings, close the diagnostic scanner, then restore the primary connection before releasing the lock.
- Known-register validation reports `supported`, `unsupported`, and `indeterminate` separately; transport failures are never treated as proof that a register is absent.
- Any entity mapping with `risk_level` is disabled by default and categorized as configuration while retaining risk metadata for expert opt-in.
- Entity platform setup is being converted away from redundant `update_before_add=True` where the coordinator has already completed its initial refresh.
- Package metadata remains at the existing release version 2.8.3; this hardening branch does not create a release implicitly.

## Verification requirement

Do not merge based on static inspection alone. The branch must pass repository lint, compile, pytest/coverage, hassfest, HACS validation, mapping validation, and new Home Assistant contract tests. Real-device soak/transport validation remains a separate hardware acceptance gate where it cannot be proven in GitHub CI.
