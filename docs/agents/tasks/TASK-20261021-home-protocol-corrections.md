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
updated_at: 2026-10-21T10:23:29+00:00
head: b65cf9fd4c4370f6f6e6f8831ed06c0729584a8c
branch: fix/home-protocol-corrections-20261021
pr: 1784
status: ready
context_routes:
  - AGENTS.md
  - claude.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/audits/home_protocol_corrections_20261021.md
  - docs/agents/evidence/home-protocol-corrections-20261021/verification.json
owned_paths:
  - custom_components/thessla_green_modbus/
  - tests/
  - tools/check_translations.py
  - CHANGELOG.md
  - docs/audits/home_protocol_corrections_20261021.md
  - docs/agents/tasks/TASK-20261021-home-protocol-corrections.md
  - docs/agents/evidence/home-protocol-corrections-20261021/
proven:
  - 'Full Python 3.13 suite: 3202 passed, 3 skipped, 0 failed.'
  - 106 HA 2026.9.2 framework/manufacturer tests passed on Python 3.14.
  - All 13 checks exited zero; source remained identical across the check sequence.
  - All 530 source/test/tool manifest files matched before commit.
  - Source fingerprint caa93f6a55dba4cd33e6602bad52e00bcb10ab4a3b3f899c4030888962a9e73e
  - Implementation commit published on the PR branch; main was not changed.
  - Existing register names/addresses, entity and unique IDs retained; unsupported legacy controls fail closed.
derived:
  - Candidate is suitable for draft review, not automatic production installation.
unknown:
  - Exact-head remote CI outcome; inspect the live run rather than assuming local PASS applies.
  - Physical acceptance of combined PR1773 and manufacturer corrections.
  - FC04/274-275 semantics and optional equipment not established by register presence.
conflicts:
  - Earlier work separately updated the private HA watchdog; integration code has not been deployed.
first_failure:
  marker: none
  evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
rejected_hypotheses:
  - A green test suite proves hardware acceptance.
  - Blocked Codex executions count as independent reviews.
changed_paths:
  - Runtime, regression tests, metadata, changelog and documentation; see b65cf9f diff against PR1773 head.
validation:
  - command: compile; ruff; imports; format; mypy
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: full-pytest
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: ha2026.9.2
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: check_translations; check_maintainability
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: validate_registers; validate_entity_mappings
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: compare_registers_with_reference; compare_airpack4_vendor_coverage
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: checkpoint validation of all task files before publication
    result: PASS
    evidence: tools/agents/checkpoint.py --tasks docs/agents/tasks --require-checkpoint validated nine tasks.
blockers:
  - Independent AI reviews were blocked before reading code; no independent PASS claimed.
  - Physical acceptance and deployment remain pending.
next_action: Verify exact-head CI and review on PR1784, then plan controlled physical acceptance with separate deployment approval; do not merge or deploy automatically.
```
