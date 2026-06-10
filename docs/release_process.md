# Release Process

Maintainer checklist for publishing a HACS-friendly release of ThesslaGreen Modbus.

---

## How HACS shows update information

HACS reads the following to display version and update data to users:

| HACS UI element | Source |
|---|---|
| Installed version | `custom_components/thessla_green_modbus/manifest.json` → `version` |
| Latest version | Latest GitHub Release tag (must match `manifest.json` `version`) |
| "What's new" / release notes | GitHub Release body text |
| Minimum HA version | `hacs.json` → `homeassistant` and `manifest.json` → `homeassistant` |
| Integration name | `hacs.json` → `name` |

No GitHub Release tag → HACS shows **no update available**, regardless of what is in `manifest.json`.

---

## Release checklist

### 1. Decide the next version

Follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

| Change type | Version bump |
|---|---|
| Bug fix, non-breaking improvement | Patch — `X.Y.Z+1` |
| New entity, service, or behavior | Minor — `X.Y+1.0` |
| Breaking change (entity IDs, service IDs, config format) | Major — `X+1.0.0` |

### 2. Update `manifest.json`

```json
"version": "X.Y.Z"
```

File: `custom_components/thessla_green_modbus/manifest.json`

Also verify these fields are present and correct:

```json
"homeassistant": "2026.1.0",
"documentation": "https://github.com/blakinio/thesslagreen",
"issue_tracker": "https://github.com/blakinio/thesslagreen/issues"
```

### 3. Update `pyproject.toml`

```toml
version = "X.Y.Z"
```

Both `manifest.json` and `pyproject.toml` must always carry the same version string.

### 4. Update `CHANGELOG.md`

- Rename `## [Unreleased]` → `## [X.Y.Z] - YYYY-MM-DD`.
- Add a new empty `## [Unreleased]` section at the top.
- Update the `[Unreleased]` link reference at the bottom of the file:
  ```
  [Unreleased]: https://github.com/blakinio/thesslagreen/compare/vX.Y.Z...HEAD
  [X.Y.Z]: https://github.com/blakinio/thesslagreen/releases/tag/vX.Y.Z
  ```

### 5. Commit the version bump

```bash
git add custom_components/thessla_green_modbus/manifest.json pyproject.toml CHANGELOG.md
git commit -m "chore: bump version to X.Y.Z"
git push origin main
```

### 6. Create the git tag

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

The tag **must** be prefixed with `v` and must exactly match `manifest.json` `version`
(e.g. `v2.8.0` for `"version": "2.8.0"`). HACS requires this format.

### 7. Create the GitHub Release

Go to **https://github.com/blakinio/thesslagreen/releases/new** and:

1. **Tag**: select the tag you just pushed (`vX.Y.Z`).
2. **Release title**: `vX.Y.Z — <short headline>` (e.g. `v2.9.0 — Fan fixes & real-device validation`).
3. **Release body**: use the template at `.github/RELEASE_TEMPLATE.md` as a starting point.
   Copy the relevant section from `CHANGELOG.md` and expand it with:
   - A 1–3 sentence summary of what changed and why it matters.
   - A **Breaking changes** block if applicable.
   - A **What's Changed** list of notable fixes and additions.
   - A **Full Changelog** compare link (generated automatically from the link refs in CHANGELOG.md).
4. Check **Set as the latest release**.
5. Click **Publish release**.

After publishing, HACS will discover the release within minutes (on the next HACS backend refresh cycle).

---

## Release notes format

Use the `.github/RELEASE_TEMPLATE.md` template. Key sections:

```markdown
## Summary
1–3 sentences: what changed and why users should update.

## Breaking changes
(omit section if none)

## What's Changed
- **Fix:** short description (#PR)
- **Add:** short description (#PR)
- **Change:** short description (#PR)

## Full Changelog
https://github.com/blakinio/thesslagreen/compare/vPREV...vNEXT
```

Keep entries concise — one line per change, linking to the PR where relevant.
Users read this in the HACS update dialog on their phone or desktop.

---

## Version source of truth

| File | Field | Role |
|---|---|---|
| `custom_components/thessla_green_modbus/manifest.json` | `version` | HA + HACS installed-version display |
| `pyproject.toml` | `version` | Python package metadata |
| Git tag | `vX.Y.Z` | HACS latest-version detection |
| GitHub Release | title / body | HACS update dialog content |
| `CHANGELOG.md` | `## [X.Y.Z]` section | Human-readable history |

All five must be consistent before a release is considered complete.

---

## Validation before tagging

Run these locally (requires Python 3.13):

```bash
python -m compileall -q custom_components/thessla_green_modbus tests tools
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
python tools/check_maintainability.py
python tools/validate_entity_mappings.py
python tools/check_translations.py
```

CI (GitHub Actions) must also be green on the release commit before tagging.

---

## Post-release

- Verify the new release appears in **https://github.com/blakinio/thesslagreen/releases**.
- Install a test instance via HACS and confirm the version badge shows `X.Y.Z`.
- If HACS does not pick up the release within 30 minutes, trigger a manual HACS refresh.
- Open a `docs/releases/vX.Y.x.md` draft file for the next release cycle.
