---
task_id: TASK-20261021-home-protocol-corrections
status: ready
branch: main
base_branch: main
created: '2026-10-21'
updated: '2026-10-21'
related_pr: 1773 (base candidate, unmerged)
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

The checkpoint head identifies the worktree parent at capture time. Fresh-read Git
and the published PR before resuming; the evidence pins the full validated source
fingerprint independently of commit metadata. No physical deployment is implied.

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-10-21T10:20:45.654650+00:00
head: 4990677c9826765aad5d80afe6d5d72c61765efb
branch: main
pr: none
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
  - 106 current HA 2026.9.2 framework/manufacturer tests passed on Python 3.14.
  - All 13 checks exited zero; code remained identical across the full check sequence.
  - Source fingerprint caa93f6a55dba4cd33e6602bad52e00bcb10ab4a3b3f899c4030888962a9e73e
  - Existing register names/addresses, entity and unique IDs are retained; unsupported legacy controls fail closed.
derived:
  - Candidate is suitable for draft review, not automatic production installation.
unknown:
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
  - Runtime, regression tests, metadata, changelog and documentation; see Git diff against PR1773 head.
validation:
  - command: compile
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: ruff
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: imports
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: format
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: mypy
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: full-pytest
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: ha2026.9.2
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: check_translations
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: check_maintainability
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: validate_registers
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: validate_entity_mappings
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
  - command: compare_registers_with_reference and compare_airpack4_vendor_coverage
    result: PASS
    evidence: docs/agents/evidence/home-protocol-corrections-20261021/verification.json
blockers:
  - Independent AI reviews were blocked before reading code.
  - Physical acceptance and deployment remain pending.
next_action: Publish the verified candidate on fix/home-protocol-corrections-20261021 as a draft PR and verify exact-head CI; no merge or deployment.
```
