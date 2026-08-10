---
task_id: TASK-20260810-ha-integration-hardening
status: implementing
branch: fix/ha-integration-hardening-20260810
base_branch: main
created: 2026-08-10
updated: 2026-08-10
related_pr: ""
owned_paths:
  - custom_components/thessla_green_modbus/**
  - tests/**
  - .github/workflows/**
  - pyproject.toml
  - requirements.txt
  - constraints.txt
  - docs/**
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
search_first:
  - async_extract_entity_ids
  - async_setup_entry
  - scan_all_registers
  - risk_level
optional_reads:
  - docs/real_device_validation.md
  - docs/ha_quality_scale_audit.md
---

# Home Assistant integration hardening

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-10T18:35:00Z
head: b1a1d21b2146467a6e12c0574f779bd8d2ad7236
branch: fix/ha-integration-hardening-20260810
pr: none
status: investigating
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
owned_paths:
  - custom_components/thessla_green_modbus/**
  - tests/**
  - .github/workflows/**
  - pyproject.toml
  - requirements.txt
  - constraints.txt
  - docs/**
proven:
  - GitHub connector has push/admin access to blakinio/thesslagreen.
  - main is b1a1d21b2146467a6e12c0574f779bd8d2ad7236.
  - Open PRs are Dependabot PRs #1759 and #1755 only.
  - No AGENTS.override.md was found.
  - AGENTS.md requires GitHub connector-first routing and durable checkpointing for substantial tasks.
derived:
  - The audit hardening can proceed on a dedicated branch without conflicting with an existing feature PR.
unknown:
  - Which previously identified audit findings still reproduce on the current main after the latest agent-governance commit.
conflicts: []
first_failure:
  marker: none
  evidence: none
rejected_hypotheses:
  - GitHub connector is unavailable; connector access is verified.
changed_paths:
  - docs/agents/tasks/TASK-20260810-ha-integration-hardening.md
validation:
  - command: repository preflight via GitHub connector
    result: PASS
    evidence: main and open PR state verified
blockers: []
next_action: Verify each P0 audit finding against the current main implementation and Home Assistant API contract.
```
