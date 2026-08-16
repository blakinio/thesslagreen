---
task_id: TASK-20260816-airpack-284-physical-acceptance
status: blocked
branch: test/airpack-284-acceptance-20260816
base_branch: main
created: 2026-08-16
updated: 2026-08-16
related_pr: "1772"
owned_paths:
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
  - docs/real_device_validation.md
  - docs/audits/deep_audit_2026-08-11.md
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
search_first: []
optional_reads: []
---

# AirPack 2.8.4 physical acceptance

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-16T10:12:00+02:00
head: 3ea465ee746571f957862a5ec7e4322866a7e991
branch: test/airpack-284-acceptance-20260816
pr: 1772
status: blocked
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
owned_paths:
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
  - docs/real_device_validation.md
  - docs/audits/deep_audit_2026-08-11.md
proven:
  - v2.8.4 is installed in HACS and manifest version is 2.8.4; repository tag v2.8.4 resolves to b198c626d20797978bb78dbbab1fe2934fc1dc32.
  - Live environment is HA Core 2026.8.2 on HA OS 18.1; ThesslaGreen firmware is 3.11; transport is TCP port 8899 with slave ID 10; runtime model field is Unknown.
  - Config-entry reload recovered automatically to loaded/connected; one cancelled-read warning occurred during unload/setup but no ThesslaGreen traceback followed.
  - Before advanced tests, diagnostics showed 61 successful reads, 0 failed reads, 0 connection errors and 0 timeout errors after more than 40 minutes of normal polling.
  - Twenty-one thessla_green_modbus services are registered in Home Assistant.
  - Fan 30 to 50 to 30 physically converged: supply/exhaust flow reached 165/162 m3h at 50 percent and returned to about 99/97 m3h at 30 percent.
  - Number air_flow_rate_manual 30 to 31 to 30 confirmed through register-backed state; same-state select mode and comfort-mode switch writes logged successful targeted read-back decode.
  - Diagnostics download succeeded and redacted the host and serial fields.
  - HA restart after the failed full scan stopped the transaction-ID storm; recorder restarted at 10:05:58, ThesslaGreen setup completed at 10:07:10, TCP returned connected and baseline 30 percent / 22 C was restored.
derived:
  - Repository/CI quality is not the blocker; v2.8.4 fails the physical post-hardening acceptance gate on runtime behavior.
  - Further deliberate failure/network disruption tests should be withheld on v2.8.4 because three independent release-blocking failures are already directly proven.
  - The prior developer-MCP capability blocker is resolved in this conversation and is no longer relevant.
unknown:
  - Exact AirPack model identity; live diagnostics report model Unknown.
  - Controlled unreachable/rejected write semantics and Repairs issue lifecycle on physical v2.8.4, intentionally not run after blockers were found.
  - External network-loss reconnect behavior, intentionally not run after blockers were found.
  - 24 to 72 hour soak result on a fixed candidate.
  - RTU/USB behavior; this session used TCP only.
conflicts: []
first_failure:
  marker: climate-target-nonconvergence
  evidence: climate.set_temperature 22.5 returned success/optimistic 22.5, but an explicit refresh confirmed required_temperature remained 22.0; a later 23.0 test again exposed optimistic state without matching the independent physical register sensor.
rejected_hypotheses:
  - repository CI is sufficient evidence for physical AirPack acceptance.
  - the prior developer-MCP conversation gate still blocks live acceptance; Home_assistant calls are now executing successfully.
  - fan write hardening remains broken; the physical 30 to 50 to 30 test converged correctly.
  - validate_known_registers failure is an MCP response-only limitation; HA logs show a real integration TypeError in handlers_data.py.
  - full scan isolation prevents transaction-ID mismatch on this device; batch 4 with 150 ms pacing produced a sustained mismatch storm.
changed_paths:
  - docs/real_device_validation.md
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
validation:
  - command: installed build identity and release-tag inspection
    result: PASS
    evidence: HACS v2.8.4 and manifest 2.8.4; tag v2.8.4 points to b198c626d20797978bb78dbbab1fe2934fc1dc32.
  - command: config-entry reload and post-reload TCP verification
    result: PASS
    evidence: integration returned loaded, connected=true and fresh device data after setup.
  - command: normal polling baseline
    result: PASS
    evidence: 61 successful reads, 0 failed reads, 0 connection errors, 0 timeout errors before advanced tests.
  - command: physical fan 30 to 50 to 30
    result: PASS
    evidence: register-backed setpoint and measured airflow converged at both 50 and restored 30 percent.
  - command: number/select/switch read-back
    result: PASS
    evidence: number 31 and 30 verified; debug log captured targeted read-back decode for mode=1 and comfort_mode_panel=0.
  - command: climate setpoint and mode writes
    result: FAIL
    evidence: target writes showed optimistic/confirmed mismatch; fan_only to auto to fan_only caused physical fan 10 percent and required_temperature 0 until explicit restore.
  - command: validate_known_registers batch 4 delay 150 ms
    result: FAIL
    evidence: TypeError _ClientBackedTransport.read_input_registers() missing required positional argument address; no validation report produced.
  - command: isolated full scan batch 4 delay 150 ms
    result: FAIL
    evidence: sustained transaction_id mismatch storm with more than 1600 observed matching lines; scan required HA restart to terminate.
  - command: post-abort HA restart and runtime recovery
    result: PASS
    evidence: no mismatch after restart boundary; integration loaded, TCP connected, fan 30 percent, target 22 C and about 99/97 m3h restored.
  - command: controlled write failure, Repairs lifecycle and external network interruption
    result: NOT_RUN
    evidence: withheld to avoid additional disruption after three release-blocking failures were proven.
blockers:
  - Climate write path does not reliably converge physical state and HVAC mode round-trip caused unexpected output/setpoint changes.
  - validate_known_registers crashes in the active-client path with a missing-address TypeError.
  - Full isolated scan causes a severe transaction-ID mismatch storm and does not cancel promptly during HA shutdown.
next_action: Open a separate runtime-fix PR for the three proven v2.8.4 hardware defects, publish a new candidate only after deterministic CI passes, then rerun the failed and withheld physical matrix before merging PR #1772.
```
