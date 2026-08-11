# ThesslaGreen Modbus quality status

**Status date:** 2026-08-11  
**Current released version:** `2.8.3`  
**Repository quality declaration:** Home Assistant `bronze`  
**Minimum Home Assistant:** `2026.1.0`  
**Current `main` Modbus dependency:** `pymodbus>=3.6.1,<4.0`

This file is the canonical snapshot for current quality, validation, and release-readiness status. Historical audit documents may describe older commits and must not be interpreted as the current state unless explicitly marked current.

## Automated verification

The 2026-08-10 hardening sequence is complete. PR #1762 merged the primary hardening work and PR #1763 merged the final follow-up. The follow-up checkpoint was finalized on `main` as `62e3cb10894767671c7aeb33a5e62b24c82c07ff`.

The GitHub Actions run for `main@62e3cb1` completed all nine current checks successfully, including:

- Ruff/import-order/format, compilation, vendor register coverage, translations, maintainability and checkpoint validation;
- blocking `mypy` validation;
- the full pytest suite on Home Assistant `2026.2.3`;
- focused API-contract tests on the declared minimum Home Assistant `2026.1.0`;
- focused API-contract tests on current Home Assistant `2026.8.1` / Python `3.14`;
- `pymodbus` compatibility checks for `3.6.1` and `3.14.0`;
- entity mapping validation;
- Hassfest;
- HACS validation.

The full suite reported **90.78%** total coverage against the repository's configured 80% minimum. This is a useful repository gate, but it is not sufficient by itself for Home Assistant's current Silver `test-coverage` rule, which requires above 95% coverage for every integration module.

The 2026-08-11 audit verified two successive Codecov failure modes in otherwise-successful Tests jobs: the baseline upload lacked authentication, and an OIDC-authenticated retry obtained a valid short-lived token but Codecov returned `Repository not found`. Because Codecov repository onboarding/authorization is external to this repository and the upload was non-blocking, the broken upload step is removed rather than kept as a false-green signal. Pytest continues to enforce the local 80% coverage gate and print module-level coverage in CI. Codecov can be reintroduced later only after the repository is explicitly configured in Codecov and the upload is made a meaningful verified signal.

## Real-device evidence

Real-device evidence is **partial**, not complete. Existing evidence covers an AirPack 4 over Modbus TCP and predates the 2026-08-10 hardening changes. It remains useful historical evidence but does not prove post-hardening behavior.

Required external acceptance still includes:

- post-hardening TCP smoke test on a physical AirPack;
- RTU/USB validation using a stable `/dev/serial/by-id/...` path;
- reconnect/network-loss behavior;
- safe write/read-back verification;
- 24–72 hour polling soak with no transport desynchronization.

GitHub CI cannot prove these hardware conditions. They must stay explicitly `PENDING` until measured on a real unit running the post-hardening candidate.

## Deliberately deferred work

Broad read-path/mixin/module consolidation is deliberately deferred. `docs/core_consolidation_plan.md` requires longer real-device validation before further high-risk runtime restructuring. This is a safety decision, not unfinished accidental scope.

## Release status

`v2.8.3` is the current published GitHub release. Its tagged manifest declares `pymodbus>=3.6.0,<4.0`. Current `main` contains post-release hardening and declares `pymodbus>=3.6.1,<4.0` while the package version is still `2.8.3`; the next release must therefore select and apply a new version before tagging. No new release tag should be created until the repository owner intentionally selects that version and the real-device acceptance level required for the release.
