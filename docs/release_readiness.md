# Release Readiness

**Status date:** 2026-08-10  
**Current published release:** `v2.8.3`  
**Current manifest/package version:** `2.8.3`  
**Canonical quality status:** [`docs/quality/STATUS.md`](quality/STATUS.md)

This file describes readiness for the **next** release. The old May 2026 `v2.8.0` pre-release checklist is obsolete: `v2.8.3` is already published.

## Current version sources

| Source | Current value |
|---|---|
| `custom_components/thessla_green_modbus/manifest.json` | `2.8.3` |
| `pyproject.toml` | `2.8.3` |
| `hacs.json` minimum Home Assistant | `2026.1.0` |
| runtime pymodbus constraint | `>=3.6.0,<4.0` |
| repository quality declaration | `bronze` |

Version metadata was synchronized by PR #1762. Do not increment it merely because development commits exist; select the next semantic version intentionally at release time.

## Automated readiness

PR #1762 merged to `main` as `088677385a179a0a02c14ddae3dd96d20c2534e0`. Canonical CI #1146 passed:

- Ruff and import order;
- Ruff format;
- compileall;
- vendor register comparison;
- AirPack 4 vendor coverage;
- translation validation;
- maintainability gate;
- checkpoint validation;
- full pytest suite;
- entity mapping validation;
- Hassfest;
- HACS validation.

The full test suite reported 90.68% coverage, above the configured 80% minimum.

The 2026-08-10 follow-up hardening additionally requires a green final run with:

- `mypy` as a blocking gate;
- focused API-contract tests on minimum Home Assistant `2026.1.0`;
- immutable commit SHAs for external GitHub Actions;
- Hassfest with the config-entry-only schema warning removed;
- Repairs write-failure lifecycle regression tests;
- tests proving the removed volatile `total_energy` state does not return.

Until that follow-up CI is green, those additions are `PENDING`, not assumed.

## Real-device readiness

**Status: PARTIAL / external gate.**

Historical evidence exists for an AirPack 4 over Modbus TCP, but it predates the 2026-08-10 hardening changes. The next release should not claim post-hardening hardware validation until the checks in [`docs/real_device_validation.md`](real_device_validation.md) are performed.

Recommended release gate for hardware-sensitive changes:

1. Load the candidate build on a physical AirPack.
2. Verify initial discovery and normal polling.
3. Exercise representative safe writes and read-back.
4. Verify a network interruption and automatic reconnect.
5. If RTU is claimed for the release, validate with a stable `/dev/serial/by-id/...` path.
6. Run a 24–72 hour soak and inspect connection/read/write statistics and logs.
7. Record exact integration commit, Home Assistant version, device model, firmware, and transport.

## Supply-chain readiness

CI and release workflows must use immutable commit SHAs for third-party GitHub Actions. Version comments may be kept next to the SHA for readability. Moving `@main`, `@master`, or mutable major-version refs are not accepted in the final follow-up state.

## Documentation readiness

Before tagging the next release verify that all of these describe the candidate, not an old branch/version:

- `README.md` and `README_en.md`;
- `CHANGELOG.md`;
- `docs/quality/STATUS.md`;
- `docs/ha_quality_scale_audit.md`;
- `docs/real_device_validation.md`;
- this file;
- `docs/release_process.md`.

## Release decision

A new GitHub release is **not** created by this audit follow-up. The repository owner should choose the next version after deciding how much real-device validation is required for that release. The existing release workflow reads the version from `manifest.json` and will skip creation when the corresponding tag already exists.
