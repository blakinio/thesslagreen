---
task_id: TASK-20260812-quality-scale-closeout
status: validating
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
updated_at: 2026-08-12T20:20:00Z
head: ea61639645a42052b630b7a3075f53c10fda69bc
branch: test/quality-scale-coverage-20260812
pr: 1769
status: validating
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
  - Exact PR integrated CI run 31636262371 completed successfully for branch head b6144eeaed2abbc1bc63fc89c49e5f3330a14831 and merge candidate a100e78f377876d9437de376d28b64310bc86371.
  - Tests job 94247656487 reports total coverage 98.21 percent and quality-scale module gaps=0.
  - Every config-flow Python module, including config_flow.py and _config_flow/**, reports 100 percent coverage in job 94247656487.
  - Every other Python module under custom_components/thessla_green_modbus is strictly above 95 percent according to the raw coverage.json threshold evaluation in job 94247656487.
  - core/io_mixin.py and core/register_groups.py now report 100 percent coverage; no pragma/omit suppression was introduced for this closeout.
  - Coverage artifact 9157182138 records the zero-gap proof for merge candidate a100e78f377876d9437de376d28b64310bc86371; uploaded zip SHA-256 is ff909afd47577a7f25075b52cffe3010152a0d17431656a098622dc378f8967a.
  - After zero-gap proof existed, commit ea61639645a42052b630b7a3075f53c10fda69bc converted the diagnostics-only step into an enforcing regression gate: config-flow must stay at 100 percent and all other integration modules must stay above 95 percent.
  - release.yaml is SHA-pinned and now requires both the exact triggering commit to still be current main and a successful push-triggered CI run for that exact SHA before publication; no release or version bump has been performed.
  - Existing Modbus addresses/names, entity IDs, unique IDs, services, write safety, polling policy and scan policy were not intentionally changed by this closeout.
derived:
  - The repository now has measured evidence for the intended Home Assistant quality-scale coverage thresholds rather than a global-percentage proxy.
  - Enabling the regression gate only after run 31636262371 proved zero gaps avoids introducing an aspirational failing gate.
  - Repository-only validation cannot prove physical AirPack startup, reconnect, safe write/read-back or soak behavior.
unknown:
  - Exact-head CI result for the checkpoint/gate commit sequence after ea61639645a42052b630b7a3075f53c10fda69bc.
  - Physical AirPack behavior of the post-hardening candidate because no Home Assistant/AirPack connector is exposed in this session.
  - Physical firmware major.minor reporting on a device where patch is unavailable.
conflicts: []
first_failure:
  marker: final-exact-head-validation-pending
  evidence: The enforcing gate was added after the successful zero-gap proof and requires one fresh exact-head CI pass together with this refreshed checkpoint before PR readiness.
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
  - command: GitHub Actions run 31636262371 on PR branch head b6144eeaed2abbc1bc63fc89c49e5f3330a14831 / integrated merge candidate a100e78f377876d9437de376d28b64310bc86371
    result: PASS
    evidence: All CI jobs succeeded; Tests job 94247656487 reports 98.21 percent total coverage and zero quality-scale module gaps.
  - command: quality-scale coverage evaluator in Tests job 94247656487
    result: PASS
    evidence: config-flow threshold 100 percent and all other integration modules strictly above 95 percent; zero gaps.
  - command: release workflow structural inspection at branch state ea61639645a42052b630b7a3075f53c10fda69bc
    result: PASS
    evidence: exact current-main SHA check plus exact-SHA successful push CI requirement are present; release actions remain immutable-SHA pinned.
blockers:
  - Live Home Assistant/AirPack connector is not exposed in the current session, so physical acceptance cannot be executed here.
next_action: Run fresh exact-head CI with the enforcing coverage gate and refreshed checkpoint; if it is fully green, mark PR #1769 ready and complete the protected merge while preserving the physical AirPack acceptance boundary.
```
