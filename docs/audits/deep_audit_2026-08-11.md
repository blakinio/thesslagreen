# Deep integration audit — 2026-08-11

## Scope

This audit covers the current repository state, CI/release governance, the main Home Assistant integration runtime paths, and read-only evidence from the owner's running Home Assistant instance.

Repository baseline: `main@62e3cb10894767671c7aeb33a5e62b24c82c07ff` before this audit cleanup.

Follow-up synchronization on 2026-08-12: repository-local follow-ups A3 and A4 have since been implemented and merged. PR #1766 closed the redundant sensor translation path; PR #1767 closed the partial firmware-version handling gap. Current synchronized repository evidence is `main@60ca43a2ad4f7b2cb594131d43eef295a5032ad4`, with post-merge CI run `31513767565` successful. Historical runtime observations below still refer to the installed published `2.8.3` instance and therefore do not prove the post-hardening `main` candidate on physical hardware.

Important evidence boundary: the running Home Assistant instance is using published integration version `2.8.3` with `pymodbus>=3.6.0,<4.0`. Current repository `main` is still versioned `2.8.3` but contains post-release hardening and requires `pymodbus>=3.6.1,<4.0`. Runtime observations from the installed release therefore do **not** prove post-hardening `main` behavior on physical hardware.

## Executive assessment

The integration is architecturally mature for a HACS custom integration. Its strongest areas are write safety, transport compatibility, config-entry lifecycle, explicit error propagation, Repairs integration, diagnostics, and CI breadth. The main opportunities are no longer broad structural rewrites; they are measured I/O efficiency, startup latency, real-device acceptance of the post-hardening candidate, and raising per-module test coverage.

No unfinished implementation branch, open pull request, or open issue existed at the start of this audit. The previously active hardening follow-up (`TASK-20260810-ha-integration-10of10-followup.md`, PR #1763) was already complete. Its remaining hardware validation items are external acceptance gates, not abandoned code tasks.

The repository-local follow-ups created by this audit are now also complete: PR #1766 and PR #1767 are merged. The remaining high-value work is physical-device validation, measured polling/startup optimization, broader risk-focused coverage uplift, model identity, and release/version hygiene.

## Verified strengths

### Runtime architecture

- `custom_components/thessla_green_modbus/__init__.py` uses config-entry lifecycle and integration-wide service registration.
- `custom_components/thessla_green_modbus/coordinator/coordinator.py` centralizes update ownership through `DataUpdateCoordinator`.
- `custom_components/thessla_green_modbus/coordinator/update.py` serializes polling against writes through the shared I/O lock and converts transport failures into coordinator failures instead of silently publishing stale success.
- `custom_components/thessla_green_modbus/core/read_batches.py` implements bounded grouped/chunked reads with fallback behavior.
- `custom_components/thessla_green_modbus/coordinator/schedule.py` and the write-path helpers use retry/reconnect handling, explicit success/failure semantics, conservative targeted read-back, and Repairs lifecycle support.

### Compatibility and CI

Baseline `main@62e3cb1` had nine successful GitHub Actions checks. The suite covers lint/format/type checking, full tests, minimum and current Home Assistant API contracts, `pymodbus` `3.6.1` and `3.14.0`, entity mapping validation, Hassfest, HACS, and layering/package checks.

The baseline Tests job (`93778480635`) reported total coverage of **90.78%**. This passed the repository's 80% coverage gate but did not meet the current Home Assistant Silver test-coverage requirement because multiple integration modules remained below 95%.

PR #1767 follow-up validation reported **90.82%** total coverage in Tests job `93824694593`, and `scanner/firmware.py` reached **83%**, up from about **68%** in the audit baseline. This is a measurable improvement but still does not satisfy the per-module Silver target. Final PR CI run `31506176043` completed successfully on exact head `ab105b57804382c595326c415de9d0cfddb23026` after rerun attempt 2, and post-merge CI run `31513767565` completed successfully on `main@60ca43a2ad4f7b2cb594131d43eef295a5032ad4`.

### Live stability sample

Read-only diagnostics from the running Home Assistant instance showed:

- Home Assistant `2026.8.1`, Python `3.14.6`;
- integration loaded and connected over TCP;
- `337` successful reads, `0` failed reads, `0` connection errors, `0` timeout errors;
- reported success rate `100%` for the sampled statistics;
- `336` available registers;
- `113232` total registers read;
- average successful update-cycle duration about `14.258 s`;
- configured scan interval `30 s`;
- device scan duration about `22.555 s`;
- config-entry setup duration about `53.134 s`.

`113232 / 337 = 336`, so the sampled runtime statistics are consistent with every successful polling cycle reading the complete set of 336 available registers.

## Findings

### A1 — High polling cost

**FACT:** `core/runtime_io.py` reads input registers, holding registers, coils, and discrete inputs during each normal update. The live installed release reports an average successful cycle of about 14.258 s at a 30 s interval, with all 336 available registers accounted for on every successful cycle.

**INFERENCE:** A large fraction of current Modbus traffic is spent repeatedly fetching data classes that normally change far less often than temperatures, fan states, alarms, or instantaneous operating values.

**RECOMMENDATION:** design a measured fast/slow/on-demand polling model. Keep safety-critical/live telemetry in the fast path; move schedules, configuration, and other low-volatility data to a slower refresh or explicit refresh path. Validate request count, cycle time, entity freshness, reconnect behavior, and write/read-back behavior on the physical AirPack before rollout.

### A2 — Startup latency and full device scan on restart

**FACT:** `coordinator/scan.py::prepare_registers_for_setup` consumes the config-flow scan cache once, but when `enable_device_scan` remains enabled it performs a fresh full device scan on later setups. The code explicitly removes the one-time cache so subsequent Home Assistant restarts scan again. The live installed release reports a scan duration around 22.555 s and total config-entry setup around 53.134 s.

**RECOMMENDATION:** replace the unconditional restart-time full scan with a versioned/TTL cache plus explicit invalidation/revalidation rules. Preserve a manual force-rescan path. Treat this as hardware-sensitive work and benchmark before/after on the real device.

### A3 — Sensor platform startup warning and redundant translation loads

**FACT:** the audit-time Home Assistant log contained `Setup of sensor platform thessla_green_modbus is taking over 10 seconds.`

**FACT:** before the post-audit closure, `sensor.py::async_setup_entry` loaded translations once and `ThesslaGreenActiveErrorsSensor.async_added_to_hass` loaded them again, while the inspected entity logic used `_error_status_description` for state attributes and never consumed either stored translation mapping.

**ACTION — COMPLETE IN REPOSITORY:** PR #1766 removed both unused translation fetch/storage paths and added focused regression coverage requiring sensor setup not to call Home Assistant's translation loader. The change is merged to `main` and repository CI is green.

**UNKNOWN:** whether this cleanup removes the historical >10 second platform warning on a physical AirPack candidate. Device I/O and restart-time scanning remain much larger startup costs and can only be separated by remeasurement after deployment.

**RECOMMENDATION:** remeasure platform setup time and the Home Assistant log on the exact merged candidate. Do not claim the warning fixed until that real runtime evidence is recorded.

### A4 — Partial firmware identity handling completed; model identity remains incomplete

**FACT:** the audit-time live diagnostics from the installed release reported `model: Unknown`, `firmware: Unknown`, and `firmware_available: false`, while capabilities and 336 registers were successfully detected.

**FACT:** the audit baseline required all three firmware components (`major.minor.patch`) before publishing a firmware value, even though `version_patch` is absent on some older firmware while major/minor remain readable.

**ACTION — COMPLETE IN REPOSITORY:** PR #1767 changed `scanner/firmware.py` so verified `major.minor` is preserved when `version_patch` is unavailable. In that case `device.firmware` is set to the two-component value and `firmware_available` is `True`. Missing `major` or `minor` still leaves firmware unavailable, preserving fail-closed behavior for materially incomplete identity.

**FACT:** PR #1767 added focused scanner tests and raised `scanner/firmware.py` coverage to **83%** in Tests job `93824694593`. Final PR CI run `31506176043` succeeded on exact head `ab105b57804382c595326c415de9d0cfddb23026`; PR #1767 merged as `60ca43a2ad4f7b2cb594131d43eef295a5032ad4`; post-merge CI run `31513767565` succeeded on that main commit.

**UNKNOWN:** the physical AirPack has not yet been revalidated on merged `main`, so the historical live `firmware: Unknown` observation cannot yet be replaced with a physical-device result for the new partial-version logic. `model: Unknown` is also still a separate unresolved identity issue.

**RECOMMENDATION:** on the physical AirPack, verify that a device lacking `version_patch` now reports the expected `major.minor` value and remains stable through reconnect/restart. Keep model identification as a separate follow-up rather than inferring it from firmware.

### A5 — Coverage improved but remains below current Silver criteria

**FACT:** audit-baseline total coverage was 90.78%. PR #1767 follow-up validation reached **90.82%** total coverage, and `scanner/firmware.py` improved from about **68%** to **83%**.

**FACT:** multiple integration modules remain below 95%, so the repository still does not satisfy the per-module coverage expectation used by the current Silver assessment.

**RECOMMENDATION:** continue raising coverage by risk, not by line-count gaming. Prioritize low-covered transport/read paths, time handling, switches/selects/binary sensors, config-flow edge cases, and maintenance service handlers. Only claim a higher Quality Scale tier after auditing every rule for that tier.

### A6 — Codecov was a false-green signal

**FACT:** baseline Tests job `93778480635` succeeded while the Codecov upload failed with `Token required - not valid tokenless upload` because the step was non-blocking.

**FACT:** PR #1765 then proved GitHub OIDC token issuance works, but Codecov rejected the authenticated upload with `Repository not found`.

**INFERENCE:** the remaining blocker is external Codecov repository onboarding/authorization rather than GitHub Actions token issuance.

**ACTION:** this audit cleanup removes the non-functional non-blocking upload and retains the local pytest coverage gate. Reintroduce Codecov only after its repository-side configuration exists and the result is a deliberately verified signal.

### A7 — Published version metadata and post-release main differ

**FACT:** tag `v2.8.3` declares `pymodbus>=3.6.0,<4.0`; current `main` declares `pymodbus>=3.6.1,<4.0` in both `manifest.json` and `pyproject.toml`, while all three still use integration/package version `2.8.3`.

**RECOMMENDATION:** select a new semantic version before the next release and synchronize manifest, package metadata, changelog, release notes, and tag. Do not treat the installed `2.8.3` device evidence as proof of the post-release main candidate.

### A8 — Release workflow is well pinned but only loosely coupled to CI

**FACT:** `.github/workflows/release.yaml` pins third-party actions by immutable commit SHA and validates version/tag state before publishing.

**FACT:** the workflow is triggered by pushes to `main` affecting release metadata and does not itself verify that the exact release commit has completed the full CI matrix before creating the GitHub release.

**RECOMMENDATION:** either keep release publication intentionally manual or add an explicit successful-CI dependency for the exact commit before publication. Do not add a complicated release gate unless it materially improves the current branch-protection/process model.

## Deferred / external acceptance

The following are intentionally not claimed complete by repository-only testing:

- post-hardening AirPack TCP smoke test;
- physical verification that missing `version_patch` now reports `major.minor` on merged `main`;
- representative safe write plus confirmed read-back on the candidate;
- network interruption and reconnect behavior;
- RTU/USB validation if RTU is claimed for the next release;
- 24–72 hour soak on the post-hardening candidate.

These checks require the physical device and are the correct gate before high-risk polling/cache restructuring.

## Recommended execution order

1. **COMPLETE — repository:** post-audit cleanup PR #1766 merged and CI-validated.
2. **COMPLETE — repository:** partial firmware identity hardening PR #1767 merged as `60ca43a2ad4f7b2cb594131d43eef295a5032ad4`; post-merge CI `31513767565` is green.
3. Remeasure sensor-platform setup time, startup duration, and the historical >10 second warning on the exact merged candidate.
4. Validate `major.minor` firmware reporting, reconnect behavior, representative safe write/read-back, and 24–72 hour soak on the physical AirPack.
5. Build a benchmark/evidence harness for request count, polling-cycle duration, startup scan duration, and reconnect/write behavior.
6. Design fast/slow/on-demand polling from measurements and implement it behind tests, then validate on the physical AirPack.
7. Introduce a versioned/TTL device-scan cache only with explicit invalidation and force-rescan behavior.
8. Raise low-coverage, high-risk modules above 95% and then re-audit the complete current Home Assistant Quality Scale checklist.
9. Resolve remaining model identity and tighten release gating/version metadata before the next published release.
