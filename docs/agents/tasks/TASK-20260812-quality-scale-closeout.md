---
task_id: TASK-20260812-quality-scale-closeout
status: implementing
branch: test/quality-scale-coverage-20260812
base_branch: main
created: 2026-08-12
updated: 2026-08-12
related_pr: "1769"
owned_paths:
  - custom_components/thessla_green_modbus/**
  - tests/**
  - .github/workflows/ci.yaml
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
updated_at: 2026-08-12T18:25:00Z
head: 5f88321bf0231150c193e79273d96a181a86b059
branch: test/quality-scale-coverage-20260812
pr: 1769
status: implementing
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/deep_audit_2026-08-11.md
owned_paths:
  - custom_components/thessla_green_modbus/**
  - tests/**
  - .github/workflows/ci.yaml
  - .github/workflows/release.yaml
  - CHANGELOG.md
  - pyproject.toml
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/audits/deep_audit_2026-08-11.md
proven:
  - main baseline remains 07dac03e236150bcac7fb209e16d630c632c8f5c with successful post-merge CI run 31586376624.
  - exact main Tests job 94082149579 reports total coverage 90.82 percent.
  - PR #1769 is the only open pull request and is mergeable but intentionally remains draft while closeout gates are incomplete.
  - PR #1769 exact head 012f656a3f77fa6fe58e1c1c08c735b0e13d4d83 reached 92.90 percent total coverage in CI run 31625414470 before lint blocked the matrix.
  - CI run 31625414470 failed in Ruff on newly added quality-scale tests; HACS and Hassfest succeeded and downstream test jobs were skipped.
  - commit 5f88321bf0231150c193e79273d96a181a86b059 fixes the directly observed syntax, import-order, unused-binding, and datetime lint findings that could be repaired from exact job evidence.
  - .github/workflows/ci.yaml currently emits per-module and config-flow coverage diagnostics from coverage.json but does not yet fail the build on the quality-scale thresholds.
  - release.yaml is SHA-pinned but still requires exact-commit full-CI publication gating before the release-hygiene objective is complete.
derived:
  - global coverage alone is insufficient for an honest higher quality-scale claim.
  - the diagnostics-only coverage step is appropriate until every module actually satisfies the intended threshold; enforcement must be added only after that evidence exists.
  - risk-focused tests should close real branches rather than suppressing coverage with pragmas or omit rules.
unknown:
  - exact per-module coverage after the latest test additions because the current branch has not yet completed a full exact-head Tests job.
  - physical AirPack behavior of the post-hardening candidate because no Home Assistant/AirPack connector is exposed in this session.
  - whether all current Home Assistant Bronze/Silver checklist rules are already satisfied beyond the known coverage and hardware-evidence gaps.
conflicts: []
first_failure:
  marker: exact-head-ci-not-yet-green
  evidence: run 31625414470 failed in Ruff on head 012f656a3f77fa6fe58e1c1c08c735b0e13d4d83; fixes are now on 5f88321bf0231150c193e79273d96a181a86b059 and require fresh exact-head validation.
rejected_hypotheses:
  - global coverage above 90 percent is sufficient for the current Home Assistant quality-scale test rule.
  - pragma no cover or coverage omission is an acceptable substitute for exercising reachable logic.
  - a diagnostics-only coverage report is equivalent to a regression gate.
  - hardware-sensitive polling/cache defaults should be changed without physical-device measurements.
changed_paths:
  - .github/workflows/ci.yaml
  - .github/workflows/release.yaml
  - custom_components/thessla_green_modbus/core/transport_select.py
  - custom_components/thessla_green_modbus/registers/parser.py
  - custom_components/thessla_green_modbus/registers/schema.py
  - pyproject.toml
  - tests/test_quality_scale_capabilities_remaining.py
  - tests/test_quality_scale_climate_remaining.py
  - tests/test_quality_scale_coordinator_scan_remaining.py
  - tests/test_quality_scale_fan_remaining.py
  - tests/test_quality_scale_remaining_helpers.py
  - tests/test_quality_scale_remaining_small_runtime.py
  - tests/test_quality_scale_scanner_firmware_remaining.py
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
validation:
  - command: GitHub Actions run 31586376624 on main@07dac03e236150bcac7fb209e16d630c632c8f5c
    result: PASS
    evidence: full main CI completed successfully; Tests job 94082149579 is the baseline.
  - command: GitHub Actions run 31625414470 on PR head 012f656a3f77fa6fe58e1c1c08c735b0e13d4d83
    result: FAIL
    evidence: HACS and Hassfest passed; Ruff failed on quality-scale test lint/syntax findings and downstream matrix jobs were skipped.
blockers:
  - live Home Assistant/AirPack connector is not exposed in the current session, so physical acceptance cannot be executed here.
next_action: Run exact-head CI for the refreshed PR branch, repair only concrete remaining failures, then use the completed coverage.json evidence to close any modules still at or below 95 percent and config-flow modules below 100 percent before enabling the regression gate.
```
