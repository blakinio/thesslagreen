---
task_id: TASK-20260810-ha-integration-10of10-followup
status: ready
branch: main
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
updated_at: 2026-08-11T12:15:28Z
head: bdcfce297f48670024987e04d08a22f1f16aeb37
branch: main
pr: 1763
status: ready
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
  - PR #1763 was squash-merged to main as bdcfce297f48670024987e04d08a22f1f16aeb37.
  - Pre-merge canonical CI #1261 passed all 9 repository jobs on head 221fb6a920d8d8b39ba64a5573f352f892fb28b2.
  - Post-merge canonical CI #1262 passed all 9 repository jobs on main commit bdcfce297f48670024987e04d08a22f1f16aeb37.
  - Full pytest/coverage passed after merge with 90.78 percent coverage against the enforced 80 percent threshold.
  - Home Assistant contract jobs passed for minimum 2026.1.0 and current 2026.8.1.
  - pymodbus compatibility jobs passed for 3.6.1 and 3.14.0; runtime metadata declares pymodbus>=3.6.1,<4.0.
  - Runtime pydantic dependency is declared consistently and clean Home Assistant contract jobs import the integration successfully.
  - Config-entry and device-registry identity now prefer stable serial identity while mutable endpoint fields remain duplicate-match data.
  - RTU reconfigure handles serial_port, baud_rate, parity, stop_bits and slave_id instead of using the TCP-only schema.
  - Targeted write read-back no longer shadows Home Assistant async_set_updated_data and confirmed values update coordinator state.
  - Final Modbus write failure creates an actionable Repairs issue and a later successful write clears it.
  - CI and release actions are pinned to immutable SHAs; actions/setup-python v7.0.0 is pinned to 5fda3b95a4ea91299a34e894583c3862153e4b97.
  - Release workflow run #13 for the merged main commit completed successfully.
  - Superseded Dependabot PRs #1755 and #1759 were closed after their intended changes were verified present on main.
  - Repository search after cleanup returned zero open pull requests and zero open issues.
derived:
  - The bounded repository hardening follow-up is complete and ready; no repository CI, PR, issue or release blocker remains.
  - Broad core/read-path consolidation remains a separate hardware-gated activity and should not be inferred complete from CI.
unknown:
  - Long-soak and reconnect behavior of the merged code on a physical ThesslaGreen AirPack over real TCP/USB-RTU hardware.
conflicts: []
first_failure:
  marker: none-after-final-validation
  evidence: CI #1261 and post-merge CI #1262 both completed successfully; no repository gate remains failed.
rejected_hypotheses:
  - Real-device validation can be inferred from GitHub CI.
  - IP address or mutable hostname is an acceptable Home Assistant config-entry unique_id.
  - A successful Modbus read-back automatically updates coordinator.data when a mixin shadows DataUpdateCoordinator.async_set_updated_data.
  - The old Dependabot PRs remained necessary after #1763 merged equivalent pinned dependency changes.
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
validation:
  - command: canonical pre-merge CI #1261
    result: PASS
    evidence: all 9 jobs passed on 221fb6a920d8d8b39ba64a5573f352f892fb28b2, including full pytest, HA 2026.1.0/2026.8.1 and pymodbus 3.6.1/3.14.0.
  - command: canonical post-merge CI #1262
    result: PASS
    evidence: all 9 jobs passed on main commit bdcfce297f48670024987e04d08a22f1f16aeb37.
  - command: full pytest with coverage on main
    result: PASS
    evidence: pytest job passed and reported 90.78 percent total coverage against an 80 percent required threshold.
  - command: release workflow run #13
    result: PASS
    evidence: release workflow completed successfully for bdcfce297f48670024987e04d08a22f1f16aeb37.
  - command: repository open-work search
    result: PASS
    evidence: GitHub searches returned zero open pull requests and zero open issues after closing superseded #1755 and #1759.
blockers: []
next_action: Before any broad core/read-path consolidation, execute the physical AirPack soak/reconnect plan in docs/real_device_validation.md and record the hardware evidence.
```
