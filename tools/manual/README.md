# Manual / one-shot tools

Scripts in this directory are **not** part of the automated pipeline (CI,
pre-commit, or the `tools/` validators referenced by `CLAUDE.md`). They are
one-shot maintenance or migration utilities that were run manually at a point
in time and are kept here for reference and reuse.

They are intentionally separated from `tools/` so that the top-level `tools/`
directory contains only the recurring validators/generators.

| Script | Purpose | When to run |
|---|---|---|
| `migrate_register_names.py` | Normalise register names in `thessla_green_registers_full.json` to snake_case and sort them. | Already applied; only if names drift again. |
| `translate_register_descriptions.py` | One-shot translation of `description_en` fields from Polish. | Already applied; only when adding new untranslated descriptions in bulk. |
| `clear_airflow_stats.py` | Remove legacy percentage-based airflow statistics from a Home Assistant recorder DB after upgrading. | Manually, by a user/maintainer, once after the airflow-unit change. |
| `delete_stale_branches.sh` | Bulk-delete non-protected branches in the GitHub repo via the API. | Manually, by a maintainer with a token. Review `KEEP_PATTERN` before running. |

None of these are imported by runtime code, tests, CI, or pre-commit.
