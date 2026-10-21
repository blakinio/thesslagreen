# Scoped independent review and resolution — 2026-10-21

Three explicitly authorized Codex CLI sessions reviewed source supplied in the prompt,
pinned at `72ea7759c4062753e3173a301a1e602bb1692b72`. The reviewers made zero tool
calls and did not run tests, access HA or inspect files. This is a completed scoped
static review, not full candidate approval. Previous blocked attempts remain blocked.
Original report hashes and automated follow-up checks are in `review-verification.json`.

| Finding | Resolution | Regression evidence |
| --- | --- | --- |
| Home AFC/duct procedure excluded despite both PDFs documenting configuration mode 65 | Accept an explicitly selected Home or AP4 profile, with equipment confirmation and discovered register required. Unknown profiles still reject. No procedure executed on hardware. | `test_documented_home_and_ap4_afc_test_requires_equipment_confirmation`, `test_unknown_family_cannot_start_afc_test` |
| Queued poll could reopen transport after shutdown began | Recheck shutdown immediately after acquiring the write lock; the outer finally clears update-in-progress. | `test_waiting_update_does_not_restart_after_shutdown` |
| Concurrent same-slot service calls could mix settings and start time | The complete non-contiguous settings/time sequence holds the common coordinator transport lock. This is host-side serialization, not a claim of one atomic Modbus request. | `test_concurrent_slot_edits_cannot_mix_settings_and_time` |
| Partial schedule failure left changed settings without reconciliation | Refresh after every attempted operation outside the transport lock, including cancellation; propagate failure and explicitly warn that settings may have changed. Do not invent a rollback. | `test_partial_slot_change_is_reconciled_after_lock_release`, `test_reconciliation_failure_cannot_mask_partial_failure` |
| AATT decoder accepted invalid 0%/0 C and 150% values | Decode only documented 10..100% and 10..45 C words; reject overflow/bools and preserve valid boundaries. | `test_out_of_contract_aatt_is_not_a_plausible_setting`, `test_documented_aatt_boundaries_roundtrip` |

Regression tests live in `tests/test_review_regressions.py`. Additional negative paths
in `tests/test_protocol_safety_edges.py` cover transport preflight, profile/raw writes,
invalid durations, missing registers and failure reporting. The old tests that asserted
invalid decoder outputs or skipped reconciliation after a partial edit were corrected
against the documented contracts, not deleted to hide failures.

CI for the original candidate failed its existing per-module coverage gate although
all tests passed. The follow-up includes that exact gate locally and covers all
modules above its required thresholds. The duplicate, unreachable offset check was
removed after the unchanged centralized upfront guard; no validation was removed.

Unreviewed limitations: the private HA watchdog, optional equipment, physical controller
behavior, and the manufacturer's contradictory FC04/274-275 wording. Review hypotheses
about stale lower-level polling are not presented as demonstrated defects. Controlled
physical acceptance and exact-head remote CI remain required before release/merge.
