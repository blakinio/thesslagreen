---
task_id: TASK-20260812-quality-scale-closeout
status: implementing
branch: test/quality-scale-coverage-20260812
base_branch: main
created: 2026-08-12
updated: 2026-08-12
related_pr: ""
owned_paths:
  - custom_components/thessla_green_modbus/**
  - tests/**
  - .github/workflows/release.yaml
  - CHANGELOG.md
  - pyproject.toml
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/audits/deep_audit_2026-08-11.md
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/deep_audit_2026-08-11.md
search_first: []
optional_reads: []
---

# Quality-scale and release closeout

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-12T11:18:00Z
head: 07dac03e236150bcac7fb209e16d630c632c8f5c
branch: test/quality-scale-coverage-20260812
pr: none
status: implementing
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/deep_audit_2026-08-11.md
owned_paths:
  - custom_components/thessla_green_modbus/**
  - tests/**
  - .github/workflows/release.yaml
  - CHANGELOG.md
  - pyproject.toml
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/audits/deep_audit_2026-08-11.md
proven:
  - main baseline 07dac03e236150bcac7fb209e16d630c632c8f5c has successful post-merge CI run 31586376624.
  - exact main Tests job 94082149579 reports total coverage 90.82 percent.
  - scanner/firmware.py coverage is 83 percent after PR #1767.
  - core/read_bits.py coverage is 19 percent and core/transport_select.py coverage is 53 percent on the baseline.
  - multiple config-flow modules remain below 100 percent coverage.
  - official Home Assistant quality-scale rules require above 95 percent coverage for every integration module and full config-flow test coverage.
  - release.yaml is SHA-pinned but can publish from a main push touching manifest or CHANGELOG without an explicit exact-commit successful-CI verification step.
  - no open PRs or issues existed at task start.
derived:
  - global coverage alone is insufficient for an honest higher quality-scale claim.
  - risk-focused tests should close real branches rather than suppressing coverage with pragmas or omit rules.
  - release publication should fail closed on exact-commit CI evidence before any future version bump.
unknown:
  - physical AirPack behavior of post-hardening main because no Home Assistant connector is exposed in this session.
  - whether all current Home Assistant Bronze/Silver checklist rules are already satisfied beyond the known coverage gaps.
  - whether model identity can be resolved without new physical-device/vendor evidence.
conflicts: []
first_failure:
  marker: quality-scale-coverage-gap
  evidence: baseline exact-main coverage is 90.82 percent with multiple modules below the required per-module threshold and config-flow modules below full coverage.
rejected_hypotheses:
  - global 90.82 percent is sufficient for the current Home Assistant quality-scale test rule.
  - pragma no cover or coverage omission is an acceptable substitute for exercising reachable logic.
  - hardware-sensitive polling/cache defaults should be changed without physical-device measurements.
changed_paths:
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
validation:
  - command: GitHub Actions run 31586376624 on main@07dac03e236150bcac7fb209e16d630c632c8f5c
    result: PASS
    evidence: full main CI completed successfully; Tests job 94082149579 is the coverage baseline.
blockers:
  - live Home Assistant/AirPack connector is not exposed in the current session, so physical acceptance cannot be executed here.
next_action: Add focused branch tests for the lowest-covered transport/read helpers and run the complete CI matrix to establish the next measured coverage baseline.
```
