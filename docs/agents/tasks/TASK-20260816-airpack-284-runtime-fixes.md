---
task_id: TASK-20260816-airpack-284-runtime-fixes
status: implementing
branch: fix/airpack-284-hardware-blockers-20260816
base_branch: main
created: 2026-08-16
updated: 2026-08-16
related_pr: ""
owned_paths:
  - custom_components/thessla_green_modbus/services/handlers_data.py
  - custom_components/thessla_green_modbus/scanner/orchestration.py
  - custom_components/thessla_green_modbus/climate.py
  - tests/test_services_data.py
  - tests/test_quality_scale_services_data_remaining.py
  - tests/test_scan_safe_mode.py
  - tests/test_climate_optimistic.py
  - tests/test_climate.py
  - docs/agents/tasks/TASK-20260816-airpack-284-runtime-fixes.md
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
  - docs/architecture/write_path.md
search_first:
  - validate_known_registers
  - run_full_scan
  - required_temperature
  - airflow_rate_change_flag
  - temperature_change_flag
optional_reads:
  - docs/audits/targeted_readback_write_path_audit.md
  - docs/airpack4_register_exposure_policy.md
---

# AirPack 2.8.4 runtime fixes

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-16T10:15:00+02:00
head: b198c626d20797978bb78dbbab1fe2934fc1dc32
branch: fix/airpack-284-hardware-blockers-20260816
pr: none
status: investigating
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
  - docs/architecture/write_path.md
owned_paths:
  - custom_components/thessla_green_modbus/services/handlers_data.py
  - custom_components/thessla_green_modbus/scanner/orchestration.py
  - custom_components/thessla_green_modbus/climate.py
  - tests/test_services_data.py
  - tests/test_quality_scale_services_data_remaining.py
  - tests/test_scan_safe_mode.py
  - tests/test_climate_optimistic.py
  - tests/test_climate.py
  - docs/agents/tasks/TASK-20260816-airpack-284-runtime-fixes.md
proven:
  - Physical v2.8.4 acceptance on 2026-08-16 reproduced three blockers: climate confirmed-state divergence, validate_known_registers TypeError, and full-scan transaction-ID storm.
  - validate_known_registers resolves transport.read_input_registers through _get_client_method and then routes that transport wrapper through DeviceClient._call_modbus as if it were a raw pymodbus method, producing the live missing-address TypeError.
  - run_full_scan explicitly passes scanner._client into input/holding reads; resolve_transport_and_client then disables scanner._transport, bypassing transport reconnect/reset handling on the full-scan word path.
  - Existing scanner regression tests already document stale in-flight TCP responses as a transaction-ID mismatch cause after cancelled/failed batch reads.
  - Climate optimistic state currently clears only when confirmed state equals the pending request; live hardware proved a post-write refresh can confirm a different device value while the optimistic value remains visible.
derived:
  - The validate_known_registers and full-scan failures have deterministic code-path fixes that do not require register-map or public-contract changes.
  - Climate UI convergence requires at least clearing a pending command after the post-write refresh confirms current device state, but physical register write semantics must be verified before changing the Modbus sequence.
unknown:
  - Whether required_temperature/comfort_temperature writes require a vendor change-flag trigger on this firmware.
  - Whether mode changes require restoring or explicitly rewriting airflow/temperature setpoints by vendor contract.
conflicts: []
first_failure:
  marker: climate-target-nonconvergence
  evidence: physical 2.8.4 write returned optimistic target while independent required_temperature remained at the prior physical value after refresh.
rejected_hypotheses:
  - validate_known_registers is failing only in HA-MCP; the Home Assistant traceback proves an integration TypeError.
  - full scan remains on isolated transport lifecycle; the orchestration code explicitly forces the raw scanner client for word reads.
changed_paths:
  - docs/agents/tasks/TASK-20260816-airpack-284-runtime-fixes.md
validation:
  - command: physical acceptance evidence in PR #1772
    result: FAIL
    evidence: three direct runtime blockers recorded in docs/real_device_validation.md on acceptance branch.
blockers: []
next_action: Implement and regression-test the validate_known_registers active-transport dispatch fix, then fix full-scan word reads to preserve transport ownership.
```
