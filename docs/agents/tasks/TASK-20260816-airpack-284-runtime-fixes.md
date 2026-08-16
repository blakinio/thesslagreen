---
task_id: TASK-20260816-airpack-284-runtime-fixes
status: validating
branch: fix/airpack-284-hardware-blockers-20260816
base_branch: main
created: 2026-08-16
updated: 2026-08-16
related_pr: "1773"
owned_paths:
  - custom_components/thessla_green_modbus/services/handlers_data.py
  - custom_components/thessla_green_modbus/scanner/io_core.py
  - custom_components/thessla_green_modbus/climate.py
  - tests/test_quality_scale_services_data_remaining.py
  - tests/unit/test_scanner_io_core.py
  - tests/test_climate_optimistic.py
  - tests/test_climate.py
  - tests/test_quality_scale_climate_remaining.py
  - docs/agents/tasks/TASK-20260816-airpack-284-runtime-fixes.md
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
  - docs/architecture/write_path.md
search_first:
  - validate_known_registers
  - resolve_transport_and_client
  - required_temperature
  - supply_air_temperature_manual
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
updated_at: 2026-08-16T10:36:00+02:00
head: ec3a4b4c2efcb3cbc4939e36ef631b128a94e08a
branch: fix/airpack-284-hardware-blockers-20260816
pr: 1773
status: validating
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
  - docs/architecture/write_path.md
owned_paths:
  - custom_components/thessla_green_modbus/services/handlers_data.py
  - custom_components/thessla_green_modbus/scanner/io_core.py
  - custom_components/thessla_green_modbus/climate.py
  - tests/test_quality_scale_services_data_remaining.py
  - tests/unit/test_scanner_io_core.py
  - tests/test_climate_optimistic.py
  - tests/test_climate.py
  - tests/test_quality_scale_climate_remaining.py
  - docs/agents/tasks/TASK-20260816-airpack-284-runtime-fixes.md
proven:
  - Physical v2.8.4 acceptance on 2026-08-16 reproduced three blockers: climate confirmed-state divergence, validate_known_registers TypeError, and full-scan transaction-ID storm.
  - validate_known_registers resolved transport.read_input_registers and then routed that transport wrapper through DeviceClient._call_modbus as if it were a raw pymodbus method. The live traceback exactly matched the resulting missing-address TypeError.
  - handlers_data now calls owned transport methods directly with slave_id/address/count and only uses DeviceClient._call_modbus for raw client methods; a focused regression test locks this dispatch boundary.
  - Scanner full word reads passed scanner._client explicitly; the previous resolve_transport_and_client logic treated any explicit client as external and disabled scanner._transport, bypassing transport reconnect/reset semantics.
  - resolve_transport_and_client now preserves scanner transport ownership when the explicit client is scanner._client; only a genuinely external client can bypass the transport. Focused tests cover both cases.
  - Vendor-backed register definitions identify required_temperature at FC03/8190 as read-only and supply_air_temperature_manual at FC03/4212 as read-write.
  - Live hardware test proved the canonical permanent temperature path: writing number.thesslagreen_supply_air_temperature_manual 22.0 -> 22.5 followed by refresh changed sensor.thesslagreen_required_temperature and climate target to 22.5; restoring 22.0 restored both. No temperature change flag was needed for this manual setpoint.
  - The existing temporary-temperature helper remains a distinct 3-register contract using cfg_mode_2 + supply_air_temperature_temporary_4404 + temperature_change_flag, so that trigger is retained only for temporary mode.
  - Live hardware test proved AUTO -> FAN_ONLY mode-only transition does not apply stored manual outputs: the controller kept air_flow_rate_manual=30 and supply_air_temperature_manual=22 while physical fan/required-temperature stayed near 10 percent/0 C.
  - Rewriting those same stored manual setpoints after FAN_ONLY immediately restored physical output to about 99/97 m3h at 30 percent and required_temperature=22 C. Climate now re-commits only the already-stored, discovered manual airflow and temperature values when entering FAN_ONLY; it invents no defaults.
  - Climate permanent target writes now use supply_air_temperature_manual instead of the read-only required_temperature.
  - Climate pending command values remain visible only while the awaited full refresh is in flight; after a successful refresh, confirmed coordinator data becomes authoritative even when it differs from the request, preventing stale optimistic success from masking rejection/transformation.
derived:
  - All three physical blockers have deterministic code-path corrections without changing register addresses/names, entity IDs, unique IDs, service IDs, writable exposure, or polling policy.
  - No airflow/temperature change flag should be added to the normal manual climate path: the live canonical number writes converged without those flags, while existing code and register layout reserve the flags for temporary 3-register blocks.
unknown:
  - Whether the current code head passes the complete repository CI matrix; exact-head CI must decide this.
  - Whether the fixes pass the same physical acceptance matrix when installed as one candidate; pre-fix exploratory writes prove the intended register semantics but are not post-fix acceptance evidence.
  - Controlled unreachable/rejected write semantics, Repairs lifecycle, external network-loss recovery, 24-72 hour soak, and RTU/USB remain intentionally unvalidated on physical hardware.
conflicts: []
first_failure:
  marker: climate-target-nonconvergence
  evidence: v2.8.4 climate.set_temperature wrote a read-only status register path and could retain optimistic state after refresh; the writable manual setpoint at 4212 was independently proven to converge the physical target.
rejected_hypotheses:
  - validate_known_registers is failing only in HA-MCP; Home Assistant logged the integration TypeError itself.
  - full scan remains on isolated transport lifecycle whenever scanner._client is supplied; the previous resolver explicitly bypassed the transport in that case.
  - temperature_change_flag is required for the normal manual setpoint; direct 4212 writes converged without it, while the flag belongs to the separate temporary-temperature block.
  - AUTO -> FAN_ONLY failure means stored manual setpoints are lost; they remained 30/22 and simply had to be re-committed after the mode transition.
changed_paths:
  - custom_components/thessla_green_modbus/services/handlers_data.py
  - custom_components/thessla_green_modbus/scanner/io_core.py
  - custom_components/thessla_green_modbus/climate.py
  - tests/test_quality_scale_services_data_remaining.py
  - tests/unit/test_scanner_io_core.py
  - tests/test_climate_optimistic.py
  - tests/test_climate.py
  - tests/test_quality_scale_climate_remaining.py
  - docs/agents/tasks/TASK-20260816-airpack-284-runtime-fixes.md
validation:
  - command: physical canonical manual-temperature probe on installed v2.8.4
    result: PASS
    evidence: Scoped semantic probe only; 4212 22.0 -> 22.5 -> 22.0 was mirrored by required_temperature and climate target after explicit refreshes.
  - command: physical AUTO/FAN_ONLY stored-setpoint probe on installed v2.8.4
    result: PASS
    evidence: Scoped semantic probe only; mode-only transition left physical 10 percent/0 C despite stored 30/22, while re-committing the same stored 30/22 restored about 99/97 m3h and 22 C.
  - command: focused unit regression execution for transport dispatch, scanner ownership, climate canonical temperature setpoint, FAN_ONLY reapply, and optimistic reconciliation
    result: NOT_RUN
    evidence: Tests are committed but no local runner is used; exact-head GitHub Actions is the execution authority.
blockers:
  - Exact-head CI must pass before candidate deployment.
  - Full physical revalidation of climate, validate_known_registers, and isolated scan is required on the fixed candidate before PR merge or release promotion.
next_action: Inspect exact-head GitHub Actions, fix any deterministic failures, then deploy the exact green candidate to Home Assistant and rerun the failed physical acceptance rows while keeping PRs 1772 and 1773 draft.
```
