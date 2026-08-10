---
task_id: TASK-20260810-ha-integration-10of10-followup
status: implementing
branch: fix/ha-integration-10of10-followup-20260810
base_branch: main
created: 2026-08-10
updated: 2026-08-10
related_pr: null
owned_paths:
  - .github/workflows/**
  - custom_components/thessla_green_modbus/**
  - tests/**
  - README.md
  - README_en.md
  - docs/**
  - pyproject.toml
  - requirements*.txt
  - constraints.txt
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/ha_integration_hardening_2026-08-10.md
search_first:
  - mypy
  - async_create_issue
  - estimated_power
  - total_energy
  - 2.8.0
optional_reads:
  - docs/real_device_validation.md
  - docs/ha_quality_scale_audit.md
  - docs/release_readiness.md
  - docs/core_consolidation_plan.md
---

# Home Assistant 10/10 follow-up

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-10T22:00:00Z
head: 088677385a179a0a02c14ddae3dd96d20c2534e0
branch: fix/ha-integration-10of10-followup-20260810
pr: null
status: implementing
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/ha_integration_hardening_2026-08-10.md
  - docs/real_device_validation.md
  - docs/ha_quality_scale_audit.md
owned_paths:
  - .github/workflows/**
  - custom_components/thessla_green_modbus/**
  - tests/**
  - README.md
  - README_en.md
  - docs/**
  - pyproject.toml
  - requirements*.txt
  - constraints.txt
proven:
  - PR #1762 is merged to main as 088677385a179a0a02c14ddae3dd96d20c2534e0 and canonical CI #1146 passed.
  - Existing quality/release docs still contain stale 2.8.0/dev/pre-#1762 state.
  - Current CI tests only Home Assistant 2026.2.3 and does not execute mypy.
  - Hassfest and HACS CI actions use moving master/main refs.
  - repairs.py exposes a fix flow but repository search finds no runtime async_create_issue trigger.
  - Derived total_energy is accumulated in process memory and resets with DeviceClient lifecycle.
derived:
  - The previous hardening task is complete, but the broader audit-to-10/10 objective is not yet complete.
  - Broad core/module consolidation should remain deferred because the canonical consolidation plan explicitly blocks further read-path refactoring pending real-device validation.
unknown:
  - Whether the current codebase passes its configured mypy policy without additional fixes.
  - Post-#1762 behavior on a physical ThesslaGreen AirPack during long soak/reconnect testing.
conflicts: []
first_failure:
  marker: none
  evidence: follow-up implementation not yet validated
rejected_hypotheses:
  - All documentation was updated by PR #1762.
  - Real-device validation can be inferred from GitHub CI.
changed_paths:
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
validation:
  - command: inspect current main after PR #1762
    result: PASS
    evidence: main=088677385a179a0a02c14ddae3dd96d20c2534e0; PR #1762 merged
blockers: []
next_action: Refresh canonical docs, strengthen CI, add runtime repair issue lifecycle, and resolve volatile energy accumulation semantics without broad deferred refactoring.
```
