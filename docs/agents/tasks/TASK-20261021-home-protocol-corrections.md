---
task_id: TASK-20261021-home-protocol-corrections
status: ready
branch: fix/home-protocol-corrections-20261021
base_branch: main
created: '2026-10-21'
updated: '2026-10-21'
related_pr: '1784; extends unmerged 1773'
owned_paths:
- custom_components/thessla_green_modbus/
- tests/
- tools/check_translations.py
- CHANGELOG.md
- docs/audits/home_protocol_corrections_20261021.md
- docs/agents/tasks/TASK-20261021-home-protocol-corrections.md
- docs/agents/evidence/home-protocol-corrections-20261021/
required_reads:
- AGENTS.md
- claude.md
- docs/agents/CONTEXT_HANDOFF.md
- docs/audits/home_protocol_corrections_20261021.md
- docs/agents/evidence/home-protocol-corrections-20261021/verification.json
---

# Manufacturer-backed Home/AirPack4 protocol corrections

Implementation commit `b65cf9fd4c4370f6f6e6f8831ed06c0729584a8c` is published
in draft PR #1784. It extends #1773 at `4990677c9826765aad5d80afe6d5d72c61765efb`.
The checkpoint head pins the implementation, not this documentation-only follow-up.
Fresh-read the live PR head and CI before resuming. No merge/deployment is implied.

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-10-21T10:54:11.769295+00:00
head: 72ea7759c4062753e3173a301a1e602bb1692b72
branch: main
pr: 1784
status: ready
context_routes:
  - AGENTS.md
  - claude.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/audits/home_protocol_corrections_20261021.md
  - docs/agents/evidence/home-protocol-corrections-20261021/review-verification.json
owned_paths:
  - custom_components/thessla_green_modbus/
  - tests/
  - CHANGELOG.md
  - docs/agents/tasks/TASK-20261021-home-protocol-corrections.md
  - docs/agents/evidence/home-protocol-corrections-20261021/
  - docs/audits/home_protocol_corrections_20261021.md
proven:
  - 'Full suite: 3284 passed, 3 skipped; current HA 2026.9.2 contracts: 188 passed.'
  - All 14 local checks passed, including the unchanged per-module coverage gate.
  - Three prompt-only scoped reviews completed with zero tool calls; five findings corrected and regression tested.
  - Source fingerprint ba20d0117e8c19c77cc2dae31b84975fd5ca4bbe9da277e229ff49f0d1d9a148
derived:
  - Candidate is suitable for exact-head CI and controlled deployment preparation, not automatic merge.
unknown:
  - Physical acceptance and optional equipment.
  - FC04/274-275 semantics remain ambiguous in the supplied PDFs.
conflicts:
  - Earlier private HA watchdog changes are separate from integration-code deployment.
first_failure:
  marker: original-ci-module-coverage
  evidence: 'GitHub Actions run 39584339790; resolved locally by additional tests, not a weaker gate.'
rejected_hypotheses:
  - All passing tests imply every module satisfies the quality gate.
  - Completed scoped reviews prove hardware acceptance.
changed_paths:
  - See Git diff against parent head and independent-review.md for the reviewed follow-up.
validation:
  - command: compile, ruff, imports, format, mypy
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/review-verification.json
  - command: full-pytest and unchanged CI module-coverage gate
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/review-verification.json
  - command: ha2026.9.2 contracts
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/review-verification.json
  - command: translations, maintainability, register/entity validation, both vendor-reference checks
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/review-verification.json
blockers:
  - Exact-head remote CI and physical acceptance pending.
next_action: Publish the reviewed follow-up to PR 1784 and verify exact-head CI before controlled HA installation with rollback.

```
