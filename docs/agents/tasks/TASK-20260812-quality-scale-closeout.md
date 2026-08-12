---
task_id: TASK-20260812-quality-scale-closeout
status: ready
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
updated_at: 2026-08-12T20:28:00Z
head: 26fce1e3f9480e318efb7c47445b41b43ea7f5aa
branch: test/quality-scale-coverage-20260812
pr: 1769
status: ready
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
  - Current main baseline for this validation round is c3f2b81002d984086a31ab2b98c27514bc3b56fe; its change from the original task base is governance-only and does not overlap the owned implementation paths.
  - PR #1769 is the only open pull request, remains mergeable and draft, and has no reviews or unresolved review threads at the latest inspection.
  - Exact PR integrated CI run 31637012046 completed successfully for branch head 26fce1e3f9480e318efb7c47445b41b43ea7f5aa and merge candidate 6cbc8debc776f66c87e3c483b6f9a4d3937062d1 against current main c3f2b81002d984086a31ab2b98c27514bc3b56fe.
  - Tests job 94250471076 reports total coverage 98.21 percent and the enforcing quality-scale evaluator reports module gaps=0.
  - Every config-flow Python module, including config_flow.py and _config_flow/**, reports 100 percent coverage in job 94250471076.
  - Every other Python module under custom_components/thessla_green_modbus is strictly above 95 percent according to the raw coverage.json threshold evaluation in job 94250471076.
  - core/io_mixin.py and core/register_groups.py report 100 percent coverage; no pragma/omit suppression was introduced for this closeout.
  - Coverage artifact 9157472635 records the zero-gap proof for merge candidate 6cbc8debc776f66c87e3c483b6f9a4d3937062d1; uploaded zip SHA-256 is 12f9748f31c1bea1fc20654e1c2029fdcb8067dc66dbcacd6a55d2614f24cbd7.
  - After zero-gap proof existed, commit ea61639645a42052b630b7a3075f53c10fda69bc converted the diagnostics-only step into an enforcing regression gate: config-flow must stay at 100 percent and all other integration modules must stay above 95 percent.
  - release.yaml is SHA-pinned and now requires both the exact triggering commit to still be current main and a successful push-triggered CI run for that exact SHA before publication; no release or version bump has been performed.
  - Existing Modbus addresses/names, entity IDs, unique IDs, services, write safety, polling policy and scan policy were not intentionally changed by this closeout.
derived:
  - The repository now has measured and enforced evidence for the intended Home Assistant quality-scale coverage thresholds rather than a global-percentage proxy.
  - Enabling the regression gate only after zero-gap proof avoided introducing an aspirational failing gate.
  - Repository-only validation cannot prove physical AirPack startup, reconnect, safe write/read-back or soak behavior.
unknown:
  - Physical AirPack behavior of the post-hardening candidate because no Home Assistant/AirPack connector is exposed in this session.
  - Physical firmware major.minor reporting on a device where patch is unavailable.
conflicts: []
first_failure:
  marker: physical-airpack-acceptance-unavailable
  evidence: Repository gates are green, but no Home Assistant/AirPack connector is exposed in this session, so physical acceptance cannot be executed here.
rejected_hypotheses:
  - global coverage above 90 percent is sufficient for the current Home Assistant quality-scale test rule.
  - pragma no cover or coverage omission is an acceptable substitute for exercising reachable logic.
  - a diagnostics-only coverage report is equivalent to a regression gate.
  - the regression gate should be enabled before every module actually meets its threshold.
  - hardware-sensitive polling/cache defaults should be changed without physical-device measurements.
  - installed 2.8.3 runtime evidence proves the post-hardening branch on physical hardware.
changed_paths:
  - .github/workflows/ci.yaml
  - .github/workflows/release.yaml
  - custom_components/thessla_green_modbus/core/transport_select.py
  - custom_components/thessla_green_modbus/registers/parser.py
  - custom_components/thessla_green_modbus/registers/schema.py
  - pyproject.toml
  - tests/test_register_grouping.py
  - tests/test_quality_scale_io_mixin_contract.py
  - tests/test_quality_scale_config_flow_complete.py
  - tests/test_quality_scale_config_flow_helpers.py
  - tests/test_quality_scale_config_flow_orchestration.py
  - tests/test_quality_scale_core_reads.py
  - tests/test_quality_scale_climate_remaining.py
  - tests/test_quality_scale_fan_remaining.py
  - tests/test_quality_scale_sensor_remaining.py
  - tests/test_quality_scale_scanner_firmware_remaining.py
  - tests/test_quality_scale_scanner_io_read_remaining.py
  - tests/test_quality_scale_scanner_orchestration_remaining.py
  - tests/test_quality_scale_services_maintenance_remaining.py
  - tests/test_quality_scale_setup_remaining.py
  - tests/test_quality_scale_small_modules.py
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/audits/deep_audit_2026-08-11.md
validation:
  - command: GitHub Actions run 31637012046 on PR branch head 26fce1e3f9480e318efb7c47445b41b43ea7f5aa / integrated merge candidate 6cbc8debc776f66c87e3c483b6f9a4d3937062d1
    result: PASS
    evidence: All CI jobs succeeded against current main c3f2b81002d984086a31ab2b98c27514bc3b56fe; Tests job 94250471076 reports 98.21 percent total coverage and zero quality-scale module gaps.
  - command: enforcing quality-scale coverage evaluator in Tests job 94250471076
    result: PASS
    evidence: config-flow threshold 100 percent and all other integration modules strictly above 95 percent; zero gaps.
  - command: checkpoint validation in Lint job 94249961477
    result: PASS
    evidence: Validate agent checkpoints completed successfully on the integrated PR candidate.
  - command: release workflow structural inspection at branch state ea61639645a42052b630b7a3075f53c10fda69bc
    result: PASS
    evidence: exact current-main SHA check plus exact-SHA successful push CI requirement are present; release actions remain immutable-SHA pinned.
blockers:
  - Live Home Assistant/AirPack connector is not exposed in the current session, so physical acceptance cannot be executed here.
next_action: Require fresh exact-head CI for this checkpoint-ready commit; if fully green with unchanged head and clean review state, mark PR #1769 ready and squash-merge it, then verify post-merge main CI while preserving the physical AirPack acceptance boundary.
```
