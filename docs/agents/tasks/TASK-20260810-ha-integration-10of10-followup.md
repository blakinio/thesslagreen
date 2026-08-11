---
task_id: TASK-20260810-ha-integration-10of10-followup
status: validating
branch: fix/ha-integration-10of10-followup-20260810
base_branch: main
created: 2026-08-10
updated: 2026-08-11
related_pr: 1763
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
updated_at: 2026-08-11T07:27:00Z
head: f647086eb0eb6a39907d9c9d26045c91382f281b
branch: fix/ha-integration-10of10-followup-20260810
pr: 1763
status: validating
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
  - Follow-up PR #1763 is open on fix/ha-integration-10of10-followup-20260810.
  - CI now includes mandatory mypy, Home Assistant 2026.1.0 and current 2026.7.3 contract jobs, and pymodbus 3.6.1/3.14.0 compatibility jobs.
  - CI and release external actions are pinned to immutable commit SHAs and default CI token permissions are read-only.
  - Runtime write failures create an actionable Repairs issue and recovery clears it.
  - Volatile process-memory total_energy/estimated_power state was removed while instantaneous electrical_power remains explicit.
  - Active documentation and dependency metadata were refreshed; the real pymodbus lower bound is 3.6.1 because 3.6.0 was never published.
  - Config-flow identity now uses confirmed serial when available and connection fields only for duplicate matching; host/IP is not persisted as a unique_id.
  - Reconfigure validates candidate connection data before applying it and uses the current update-and-abort contract.
  - Canonical CI #1202 passed Ruff, format, compile, strict mypy, vendor coverage, translations, maintainability, both checkpoint validators, Hassfest, HACS, and entity mappings.
  - The remaining #1202 failures were isolated to stale regression tests and lightweight matrix jobs loading the PHCC-dependent repository conftest; commit f647086 aligns those tests with the hardened contracts and isolates the lightweight matrices.
derived:
  - Repository/CI hardening can be completed without broad core/read-path consolidation.
  - Broad core/module consolidation remains hardware-gated by docs/core_consolidation_plan.md and must not be forced before real-device validation PASS.
unknown:
  - Final full-CI result for the regression-aligned branch state.
  - Post-#1762/#1763 behavior on a physical ThesslaGreen AirPack during long soak/reconnect testing.
conflicts: []
first_failure:
  marker: pending-final-ci
  evidence: regression-aligned branch state has not yet completed canonical CI
rejected_hypotheses:
  - All documentation was updated by PR #1762.
  - Real-device validation can be inferred from GitHub CI.
  - IP address or mutable hostname is an acceptable Home Assistant config-entry unique_id.
  - The HA 2026.1.0 and pymodbus matrix failures in CI #1202 proved API incompatibility; decoded logs showed pytest exit 4 while importing the global PHCC-dependent conftest before contract tests ran.
changed_paths:
  - .github/workflows/ci.yaml
  - .github/workflows/release.yaml
  - custom_components/thessla_green_modbus/**
  - tests/**
  - README.md
  - README_en.md
  - docs/**
  - pyproject.toml
  - requirements.txt
  - requirements-dev.txt
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
validation:
  - command: strict mypy remediation
    result: PASS
    evidence: canonical CI #1202 passed mypy on the hardened config-flow implementation
  - command: canonical static and quality gates
    result: PASS
    evidence: CI #1202 passed Ruff, format, compile, vendor coverage, translations, maintainability, checkpoint validation, Hassfest, HACS, and entity mappings
  - command: final full CI
    result: NOT_RUN
    evidence: this user-authored checkpoint commit triggers canonical CI on the regression-aligned final branch state
blockers: []
next_action: Resolve any final canonical CI failure, then mark checkpoint ready and merge PR #1763 only after every repository gate passes.
```
