# Release template — vX.Y.Z

<!-- Copy this template when creating a new GitHub Release.
     Delete instruction comments before publishing.
     Keep the release body concise — it is shown in the HACS update dialog. -->

## Summary

<!-- 1–3 sentences: what changed and why users should update. -->

---

## ⚠️ Breaking changes

<!-- List any changes that require user action (entity ID renames, service renames,
     config entry migration, removed options). Omit this section if there are none. -->

- <!-- Example: Legacy entity IDs `rekuperator_*` removed — update automations. -->

---

## What's Changed

<!-- One line per notable change. Link to the PR where relevant.
     Group as Fixed / Added / Changed / Removed. -->

### Fixed

- <!-- Example: Fan percentage no longer exceeds 100 (#1682). -->

### Added

- <!-- Example: `validate_known_registers` now returns `register_classification` metadata. -->

### Changed

- <!-- Example: Advanced entities moved to `entity_category=config` (#1683). -->

### Removed

- <!-- Example: Legacy entity migration removed (idempotent since 2022). -->

---

## Not changed

<!-- Reassure users of stability for common concerns. -->

- Register addresses — unchanged
- Entity IDs — unchanged
- Unique IDs — unchanged
- Service IDs — unchanged
- Translation keys — unchanged

---

## Full Changelog

https://github.com/blakinio/thesslagreen/compare/vPREV...vX.Y.Z
