# Release Process

Maintainer checklist for publishing a HACS-friendly ThesslaGreen Modbus release.

**Current published release as of 2026-08-10:** `v2.8.3`.

## Version and compatibility sources

| Item | Canonical source |
|---|---|
| Integration/package version | `custom_components/thessla_green_modbus/manifest.json` and `pyproject.toml` — must match |
| Minimum Home Assistant version for HACS | `hacs.json` → `homeassistant` |
| Modbus runtime dependency | `manifest.json` and `pyproject.toml` dependency declarations |
| User-facing change history | `CHANGELOG.md` and GitHub Release body |
| HACS latest version | latest published GitHub Release/tag |

Do **not** add a `homeassistant` key to `manifest.json`; the repository's minimum Home Assistant declaration for HACS lives in `hacs.json`.

## 1. Decide the next version

Use Semantic Versioning and consider user-visible behavior, not the number of commits:

| Change type | Typical bump |
|---|---|
| Bug fix / non-breaking hardening | patch |
| New entities/actions/capabilities | minor |
| Breaking entity/action/config contract | major |

The repository currently uses `2.8.3`. Development work after that release does not automatically imply a specific next version.

## 2. Update version metadata

Set the same `X.Y.Z` in:

- `custom_components/thessla_green_modbus/manifest.json` → `version`;
- `pyproject.toml` → `version`.

Also verify:

- `hacs.json` → `homeassistant` reflects the oldest version actually covered by the minimum-version CI contract;
- pymodbus bounds are consistent across manifest/package/requirements metadata;
- `CHANGELOG.md` has an `## [X.Y.Z] - YYYY-MM-DD` section.

## 3. Run release gates

The candidate commit must pass the repository CI. The current CI contract includes:

- Ruff;
- import-order validation;
- Ruff format;
- compileall;
- mypy;
- vendor register comparison;
- AirPack 4 vendor coverage;
- translation validation;
- maintainability gate;
- durable task/checkpoint validation when applicable;
- full pytest suite with coverage;
- entity mapping validation;
- minimum supported Home Assistant API-contract tests;
- Hassfest;
- HACS validation.

For hardware-sensitive changes also follow [`docs/real_device_validation.md`](real_device_validation.md). CI cannot replace a physical Modbus soak/reconnect test.

## 4. Update release documentation

Before changing the version, update at least:

- `CHANGELOG.md`;
- `README.md` / `README_en.md` when compatibility or user-facing behavior changed;
- `docs/quality/STATUS.md`;
- `docs/release_readiness.md`;
- `docs/real_device_validation.md` when new hardware evidence exists.

Never rewrite old hardware evidence as if it were measured on the new candidate. Add a new dated evidence block instead.

## 5. Merge the release commit to `main`

Use the normal protected PR path and require all mandatory checks to pass. Do not tag a red or unreviewed candidate.

## 6. Automated GitHub Release workflow

`.github/workflows/release.yaml` is triggered by:

- `workflow_dispatch`; or
- a push to `main` that changes `manifest.json` or `CHANGELOG.md`.

The workflow:

1. reads `manifest.json` → `version`;
2. validates the version format;
3. extracts the matching section from `CHANGELOG.md` when available;
4. checks whether `vX.Y.Z` already exists;
5. if the tag does not exist, creates the GitHub Release with `tag_name: vX.Y.Z` targeted at the triggering `main` commit.

The release action and checkout action are pinned to immutable commit SHAs. Keep them pinned when upgrading; update the SHA intentionally after reviewing the upstream release/tag.

## 7. Manual fallback

If release automation is deliberately disabled or fails for a reason unrelated to the candidate code, the equivalent manual sequence is:

```bash
git checkout main
git pull --ff-only origin main
git tag vX.Y.Z
git push origin vX.Y.Z
```

Then create a GitHub Release from that exact tag and use the matching `CHANGELOG.md` section as the release notes. Do not use the manual path to bypass failed CI.

## 8. Post-release verification

Verify all of the following:

- GitHub shows `vX.Y.Z` as the intended release;
- the release points to the intended `main` commit;
- HACS discovers the new release;
- a clean HACS install reports the expected version;
- `manifest.json`, `pyproject.toml`, release tag, release title, and changelog agree;
- no documentation still advertises an older version as current.

When a release contains transport/write/scanner changes, record a post-release physical-device smoke test separately from CI evidence.

## Current release history note

The previous one-time `v2.8.0` bootstrap instructions are obsolete. Releases `v2.8.1`, `v2.8.2`, and `v2.8.3` already exist; do not recreate or move those tags.
