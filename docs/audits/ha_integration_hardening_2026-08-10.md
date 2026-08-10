# Home Assistant integration hardening — 2026-08-10

Status: final canonical CI validation

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
- Entity platform setup no longer requests redundant `update_before_add=True` where the coordinator has already completed its initial refresh.
- Fan writes now reject missing/unavailable write paths and surface rejected/failed writes instead of returning a false Home Assistant success.
- Package metadata remains at the existing release version 2.8.3; this hardening branch does not create a release implicitly.

## Automated verification evidence

- Functional hardening head: `5af39b91b6f2fc2b84e363a483b5463bfed780d5`.
- GitHub compare against `main`: branch was 107 commits ahead and 0 behind at that functional head.
- Focused final runner `31432840105` passed Ruff formatting/checks plus `pytest -q tests/test_fan.py tests/test_scan_safe_mode.py tests/test_scan_service_isolation.py` before committing the final fan/scan patch.
- The temporary verification workflows removed themselves from the committed functional head after that success.
- Earlier canonical CI iterations established green Ruff, format, compile, vendor coverage, translation, maintainability, Hassfest, HACS, and entity-map gates while failures were iteratively corrected. A final canonical full repository CI run on the finalized checkpoint/CI configuration remains the automated closure gate.

## Remaining acceptance boundary

Do not merge based on focused/static verification alone. The finalized branch must pass the canonical repository lint, compile, pytest/coverage, Hassfest, HACS validation, entity mapping validation, checkpoint validation, and Home Assistant contract tests. Real-device soak/transport validation remains a separate hardware acceptance gate because GitHub CI cannot prove behavior against the physical ThesslaGreen controller.
