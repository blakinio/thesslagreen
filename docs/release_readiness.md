# Release Readiness

**Status date:** 2026-08-11  
**Current published release:** `v2.8.3`  
**Current `main` manifest/package version:** `2.8.3`  
**Canonical quality status:** [`docs/quality/STATUS.md`](quality/STATUS.md)

This file describes readiness for the **next** release. The old May 2026 `v2.8.0` pre-release checklist is obsolete: `v2.8.3` is already published.

## Current version sources

| Source | Current value |
|---|---|
| published tag `v2.8.3` manifest | version `2.8.3`, `pymodbus>=3.6.0,<4.0` |
| `main` `custom_components/thessla_green_modbus/manifest.json` | version `2.8.3`, `pymodbus>=3.6.1,<4.0` |
| `main` `pyproject.toml` | version `2.8.3`, `pymodbus>=3.6.1,<4.0` |
| `hacs.json` minimum Home Assistant | `2026.1.0` |
| repository quality declaration | `bronze` |

The identical `2.8.3` version string on the published tag and the post-release `main` branch is development-state metadata, not evidence that the published release contains the hardening changes. The next release must intentionally select and apply a new semantic version before tagging.

## Automated readiness

The 2026-08-10 hardening sequence is complete: PR #1762 merged the primary hardening and PR #1763 merged the final follow-up. The durable follow-up checkpoint was finalized on `main` as `62e3cb10894767671c7aeb33a5e62b24c82c07ff`.

The GitHub Actions run for `main@62e3cb1` passed all nine current checks:

- Ruff and import order;
- Ruff format;
- compileall;
- `mypy`;
- vendor register comparison and AirPack 4 vendor coverage;
- translation and maintainability validation;
- durable checkpoint validation;
- full pytest suite on Home Assistant `2026.2.3`;
- API-contract tests on minimum Home Assistant `2026.1.0`;
- API-contract tests on current Home Assistant `2026.8.1` / Python `3.14`;
- `pymodbus` `3.6.1` and `3.14.0` compatibility suites;
- entity mapping validation;
- Hassfest;
- HACS validation.

The full suite reported **90.78%** total coverage against the configured 80% repository minimum. The current Home Assistant Silver quality-scale coverage rule is stricter: every integration module must be above 95%, so a Silver claim is not currently justified by coverage evidence.

The 2026-08-11 audit verified that Codecov was not a functioning release signal. The baseline non-blocking upload failed without authentication; an OIDC-authenticated retry successfully obtained a short-lived token but Codecov returned `Repository not found`. The repository-side cleanup therefore removes the non-blocking Codecov upload. Coverage remains a blocking local pytest gate with module-level reporting in the CI log. Reintroducing external coverage reporting requires explicit Codecov repository onboarding/authorization and a separately verified upload.

## Real-device readiness

**Status: PARTIAL / external gate.**

Historical evidence exists for an AirPack 4 over Modbus TCP, but it predates the 2026-08-10 hardening changes. The next release should not claim post-hardening hardware validation until the checks in [`docs/real_device_validation.md`](real_device_validation.md) are performed against the actual post-hardening candidate.

Recommended release gate for hardware-sensitive changes:

1. Load the candidate build on a physical AirPack.
2. Verify initial discovery and normal polling.
3. Exercise representative safe writes and read-back.
4. Verify a network interruption and automatic reconnect.
5. If RTU is claimed for the release, validate with a stable `/dev/serial/by-id/...` path.
6. Run a 24–72 hour soak and inspect connection/read/write statistics and logs.
7. Record exact integration commit, Home Assistant version, device model, firmware, and transport.

## Supply-chain readiness

CI and release workflows use immutable commit SHAs for third-party GitHub Actions. Version comments may be kept next to the SHA for readability. Moving `@main`, `@master`, or mutable major-version refs are not accepted in the release-ready state.

External Codecov upload is deliberately not part of the current release gate because the repository is not yet available to the Codecov uploader. No extra OIDC permission or long-lived Codecov secret is retained merely to keep a non-blocking, non-functional step green.

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

A new GitHub release is **not** created by this audit cleanup. Select the next version only when the post-hardening candidate and the required real-device acceptance level are ready; then synchronize `manifest.json`, `pyproject.toml`, release notes, and tag metadata before publishing.
