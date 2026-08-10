---
task_id: TASK-20260810-ha-integration-hardening
status: validating
branch: fix/ha-integration-hardening-20260810
base_branch: main
created: 2026-08-10
updated: 2026-08-10
related_pr: "pending"
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
updated_at: 2026-08-10T19:05:00Z
head: d7553e0aebdc09b46de7a1cf9e9a2c8c1b011e30
branch: fix/ha-integration-hardening-20260810
pr: pending
status: validating
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
  - Base main commit is b1a1d21b2146467a6e12c0574f779bd8d2ad7236.
  - Home Assistant 2026.1 and current dev expose async one-argument async_extract_entity_ids(service_call).
  - Home Assistant entity service schemas support entity, device, area, floor, and label targets.
  - Service actions are required to be registered from integration async_setup rather than per-config-entry setup.
  - Pre-change target resolution, service lifecycle, silent-write failure, concurrent diagnostic scan, transport classification, risky entity defaults, and package metadata issues reproduced in source.
  - Target resolution and schemas now use the current Home Assistant contract.
  - Services now register process-wide from async_setup and survive config-entry unload.
  - Service write failures now surface HomeAssistantError and invalid/unsupported operations surface ServiceValidationError.
  - Diagnostic full scan now pauses coordinator IO, disconnects the primary transport, uses the configured TCP/RTU transport for scanning, and restores the primary connection.
  - Known-register validation now separates unsupported from indeterminate transport failures.
  - risk_level entities are disabled by default through common entity policy.
  - manifest and pyproject package versions are synchronized at existing release 2.8.3; pymodbus runtime range is consistently <4.0.
derived:
  - The largest remaining risk is regression against the existing unit tests and formatting/type/HA validation gates, so CI must be the next source of truth.
unknown:
  - Current branch CI result.
  - Hardware soak behavior after the isolated-scan change.
conflicts: []
first_failure:
  marker: none
  evidence: none
rejected_hypotheses:
  - GitHub connector is unavailable; connector access is verified.
  - Missing entity_id means no service target; standard Home Assistant indirect targets prove otherwise.
changed_paths:
  - custom_components/thessla_green_modbus/__init__.py
  - custom_components/thessla_green_modbus/entity.py
  - custom_components/thessla_green_modbus/number.py
  - custom_components/thessla_green_modbus/protocols.py
  - custom_components/thessla_green_modbus/select.py
  - custom_components/thessla_green_modbus/services/**
  - custom_components/thessla_green_modbus/switch.py
  - custom_components/thessla_green_modbus/text.py
  - tests/test_service_target_contract.py
  - tests/test_integration_service_lifecycle.py
  - tests/test_scan_service_isolation.py
  - tests/test_risky_entity_defaults.py
  - pyproject.toml
  - requirements.txt
  - docs/audits/ha_integration_hardening_2026-08-10.md
validation:
  - command: GitHub compare main...fix/ha-integration-hardening-20260810
    result: PASS
    evidence: branch ahead of main with no divergence before CI
blockers: []
next_action: Open a draft pull request and use GitHub Actions failures as the verification/fix loop until all required gates pass.
```
