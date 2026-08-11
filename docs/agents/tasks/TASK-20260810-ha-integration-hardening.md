---
task_id: TASK-20260810-ha-integration-hardening
status: ready
branch: fix/ha-integration-hardening-20260810
base_branch: main
created: 2026-08-10
updated: 2026-08-10
related_pr: "1762"
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
updated_at: 2026-08-10T21:52:00Z
head: 5ad72386d195dc9a7ee48b5a5e0996233a1ec16c
branch: fix/ha-integration-hardening-20260810
pr: 1762
status: ready
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/ha_integration_hardening_2026-08-10.md
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
  - Base main commit is b1a1d21b2146467a6e12c0574f779bd8d2ad7236; branch was 121 commits ahead and 0 behind at final functional-head validation.
  - Home Assistant target resolution is awaited and supports standard indirect targets through the framework extractor.
  - Integration-wide services register from async_setup and survive config-entry unload/reload.
  - Failed or rejected Modbus writes surface HomeAssistantError; invalid or unsupported requests surface ServiceValidationError.
  - Diagnostic full scan serializes coordinator I/O, disconnects the primary transport, scans with the configured transport, and reconnects before releasing the lock.
  - Known-register validation separates explicit device-side unsupported responses from indeterminate transport failures.
  - Entities carrying risk_level are disabled by default and categorized as configuration.
  - Redundant update-before-add reads were removed where the coordinator already completed first refresh.
  - Package metadata is synchronized at existing release 2.8.3 and pymodbus runtime bounds are consistently <4.0.
  - Fan control no longer reports success for missing write paths, rejected writes, invalid percentages, or unavailable registers.
  - Focused fan/scan hardening runner 31432840105 completed successfully and committed functional head 5af39b91b6f2fc2b84e363a483b5463bfed780d5.
  - Temporary patch workflows were removed from the committed functional head.
  - Canonical CI run 31435299678 (#1145) passed lint, checkpoint validation, Hassfest, HACS, entity mappings, and the full pytest suite on functional head 5ad72386d195dc9a7ee48b5a5e0996233a1ec16c; total coverage was 90.68% against the 80% gate.
derived:
  - Automated repository acceptance gates are satisfied for functional head 5ad72386d195dc9a7ee48b5a5e0996233a1ec16c; this checkpoint-only finalization commit requires the normal PR CI before merge.
unknown:
  - Real-device hardware soak and transport behavior after the isolated-scan change.
conflicts: []
first_failure:
  marker: none
  evidence: Canonical CI run 31435299678 completed all mandatory jobs successfully on the finalized functional code.
rejected_hypotheses:
  - GitHub connector is unavailable; connector access is verified.
  - Missing entity_id means no service target; standard Home Assistant indirect targets are supported.
  - Every Modbus exception proves a register is unsupported; only explicit device-side error responses are classified unsupported while transport failures are indeterminate.
changed_paths:
  - .github/workflows/ci.yaml
  - custom_components/thessla_green_modbus/__init__.py
  - custom_components/thessla_green_modbus/entity.py
  - custom_components/thessla_green_modbus/climate.py
  - custom_components/thessla_green_modbus/fan.py
  - custom_components/thessla_green_modbus/number.py
  - custom_components/thessla_green_modbus/select.py
  - custom_components/thessla_green_modbus/services/**
  - custom_components/thessla_green_modbus/switch.py
  - custom_components/thessla_green_modbus/text.py
  - custom_components/thessla_green_modbus/time.py
  - tests/test_service_target_contract.py
  - tests/test_integration_service_lifecycle.py
  - tests/test_scan_service_isolation.py
  - tests/test_scan_safe_mode.py
  - tests/test_fan.py
  - tests/test_risky_entity_defaults.py
  - tests/test_entity_write_error_contract.py
  - tests/test_text.py
  - pyproject.toml
  - requirements.txt
  - docs/audits/ha_integration_hardening_2026-08-10.md
validation:
  - command: GitHub compare main...fix/ha-integration-hardening-20260810
    result: PASS
    evidence: branch ahead_by=121 and behind_by=0 at final functional head validation
  - command: ruff format/check on fan.py, test_fan.py, test_scan_safe_mode.py
    result: PASS
    evidence: GitHub Actions run 31432840105 step Extract and apply bounded patch
  - command: pytest -q tests/test_fan.py tests/test_scan_safe_mode.py tests/test_scan_service_isolation.py
    result: PASS
    evidence: GitHub Actions run 31432840105 step Verify focused regressions
  - command: canonical full repository CI
    result: PASS
    evidence: GitHub Actions run 31435299678 (#1145); lint, Hassfest, HACS, entity mappings, full pytest and 90.68% coverage all passed
blockers: []
next_action: PR #1762 is merged; before any broad core/read-path consolidation, execute the physical AirPack soak/reconnect plan in docs/real_device_validation.md and record the hardware evidence.
```
