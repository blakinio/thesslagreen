# Deep integration audit — 2026-08-11

## Scope

This audit covers the current repository state, CI/release governance, the main Home Assistant integration runtime paths, and read-only evidence from the owner's running Home Assistant instance.

Repository baseline: `main@62e3cb10894767671c7aeb33a5e62b24c82c07ff` before this audit cleanup.

Important evidence boundary: the running Home Assistant instance is using published integration version `2.8.3` with `pymodbus>=3.6.0,<4.0`. Current repository `main` is still versioned `2.8.3` but contains post-release hardening and requires `pymodbus>=3.6.1,<4.0`. Runtime observations from the installed release therefore do **not** prove post-hardening `main` behavior on physical hardware.

## Executive assessment

The integration is architecturally mature for a HACS custom integration. Its strongest areas are write safety, transport compatibility, config-entry lifecycle, explicit error propagation, Repairs integration, diagnostics, and CI breadth. The main opportunities are no longer broad structural rewrites; they are measured I/O efficiency, startup latency, real-device acceptance of the post-hardening candidate, and raising per-module test coverage.

No unfinished implementation branch, open pull request, or open issue existed at the start of this audit. The previously active hardening follow-up (`TASK-20260810-ha-integration-10of10-followup.md`, PR #1763) was already complete. Its remaining hardware validation items are external acceptance gates, not abandoned code tasks.

## Verified strengths

### Runtime architecture

- `custom_components/thessla_green_modbus/__init__.py` uses config-entry lifecycle and integration-wide service registration.
- `custom_components/thessla_green_modbus/coordinator/coordinator.py` centralizes update ownership through `DataUpdateCoordinator`.
- `custom_components/thessla_green_modbus/coordinator/update.py` serializes polling against writes through the shared I/O lock and converts transport failures into coordinator failures instead of silently publishing stale success.
- `custom_components/thessla_green_modbus/core/read_batches.py` implements bounded grouped/chunked reads with fallback behavior.
- `custom_components/thessla_green_modbus/coordinator/schedule.py` and the write-path helpers use retry/reconnect handling, explicit success/failure semantics, conservative targeted read-back, and Repairs lifecycle support.

### Compatibility and CI

Baseline `main@62e3cb1` had nine successful GitHub Actions checks. The suite covers lint/format/type checking, full tests, minimum and current Home Assistant API contracts, `pymodbus` `3.6.1` and `3.14.0`, entity mapping validation, Hassfest, HACS, and layering/package checks.

The baseline Tests job (`93778480635`) reported total coverage of **90.78%**. This passes the repository's 80% coverage gate but does not meet the current Home Assistant Silver test-coverage requirement because multiple integration modules remain below 95%.

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

**ACTION:** PR #1766 removes both unused translation fetch/storage paths and adds focused regression coverage requiring sensor setup not to call Home Assistant's translation loader. This is a repository-local cleanup only; CI validation and merge evidence are recorded in `TASK-20260811-post-audit-closure.md`.

**UNKNOWN:** whether this cleanup removes the historical >10 second platform warning on a physical AirPack candidate. Device I/O and restart-time scanning remain much larger startup costs and can only be separated by remeasurement after deployment.

**RECOMMENDATION:** remeasure platform setup time and the Home Assistant log on the exact post-hardening candidate. Do not claim the warning fixed until that real runtime evidence is recorded.

### A4 — Device identity remains incomplete

**FACT:** live diagnostics report `model: Unknown`, `firmware: Unknown`, and `firmware_available: false`, while capabilities and 336 registers are successfully detected.

**FACT:** `scanner/firmware.py` only publishes a formatted firmware version when major, minor, and patch are all present. The live register scan shows the patch register absent while major/minor registers are available.

**RECOMMENDATION:** decide and test a partial-version policy (for example major.minor with an explicit partial/unknown-patch marker) instead of silently collapsing partially known firmware to `Unknown`. Keep model identification separate from firmware inference.

### A5 — Coverage is good but below current Silver criteria

**FACT:** baseline total coverage is 90.78%, and multiple integration modules are below 95%.

**RECOMMENDATION:** raise coverage by risk, not by line-count gaming. Prioritize transport selection/read paths, firmware/device identification, config-flow edge cases, time handling, switches/selects, and maintenance service handlers. Only claim a higher Quality Scale tier after auditing every rule for that tier.

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
- representative safe write plus confirmed read-back on the candidate;
- network interruption and reconnect behavior;
- RTU/USB validation if RTU is claimed for the next release;
- 24–72 hour soak on the post-hardening candidate.

These checks require the physical device and are the correct gate before high-risk polling/cache restructuring.

## Recommended execution order

1. Merge the post-audit repository cleanup only after its complete PR checks are green.
2. Remeasure sensor-platform setup time and the historical >10 second warning on the exact merged candidate.
3. Build a benchmark/evidence harness for request count, polling-cycle duration, startup scan duration, and reconnect/write behavior.
4. Design fast/slow/on-demand polling from measurements and implement it behind tests, then validate on the physical AirPack.
5. Introduce a versioned/TTL device-scan cache only with explicit invalidation and force-rescan behavior.
6. Raise low-coverage, high-risk modules above 95% and then re-audit the complete current Home Assistant Quality Scale checklist.
7. Resolve partial firmware/model identification and tighten release gating/version metadata before the next published release.
