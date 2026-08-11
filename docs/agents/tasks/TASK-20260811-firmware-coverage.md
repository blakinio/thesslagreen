---
task_id: TASK-20260811-firmware-coverage
status: ready
owner: codex
scope: improve firmware identity semantics and scanner coverage without changing Modbus transport contracts
---

# Firmware identity and coverage hardening

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-11T15:16:00Z
head: 8305b482de0868698338737107f7af2d397e7e6f
branch: feat/firmware-coverage-20260811
pr: 1767
status: ready
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/deep_audit_2026-08-11.md
owned_paths:
  - custom_components/thessla_green_modbus/scanner/firmware.py
  - tests/test_device_scanner_firmware.py
  - docs/agents/tasks/TASK-20260811-firmware-coverage.md
proven:
  - main baseline is ae3cdd7195088f207f5e87c74c519bb799676233 and post-merge CI run 31503102829 passed all mandatory jobs.
  - scanner/firmware.py previously collapsed a missing version_patch to Unknown even though that register is absent on some older firmware.
  - PR #1767 preserves verified major.minor identity when patch is unavailable while missing major or minor remains an unavailable firmware condition.
  - PR #1767 does not change Modbus addresses, transport behavior, writes, entity IDs, services, or polling policy.
  - tests/test_device_scanner_firmware.py now contains 8 focused tests covering unavailable firmware, full and partial fallback, partial major.minor identity, probe-error context, missing major/minor, legacy read signature fallback, serial parsing, and ASCII device-name parsing.
  - CI run 31505010765 passed every completed mandatory job on head 8eb38e7875bc554ae7aa9045c32de985924c3331; its first Current HA job was an unusable zero-step runner state and was not counted as PASS.
  - Tests job 93824694593 in run 31505010765 completed successfully with total coverage 90.82 percent and scanner/firmware.py coverage 83 percent, up from about 68 percent in the prior audit baseline.
  - fresh CI run 31505638599 on checkpointed head 8305b482de0868698338737107f7af2d397e7e6f completed with conclusion success.
  - CI run 31505638599 passed Lint including Ruff, format, compile, mypy and checkpoint validation, Hassfest, HACS, full Tests, entity mappings, minimum HA 2026.1.0, current HA 2026.8.1, pymodbus 3.6.1, and pymodbus 3.14.0.
derived:
  - major and minor together provide useful verified firmware identity when patch is genuinely unavailable on an older unit.
  - the bounded scanner change materially improves risk-focused firmware coverage but does not by itself satisfy Home Assistant Silver per-module coverage expectations.
  - the earlier zero-step Current HA state was transient GitHub Actions runner behavior because the fresh run executed the same contract job successfully.
unknown:
  - exact physical AirPack behavior of the newest candidate; no live Home Assistant connector is currently exposed in this session.
  - post-hardening reconnect and 24-72 hour physical soak behavior.
conflicts: []
first_failure:
  marker: candidate-ci-hygiene
  evidence: CI #1282 first failed Ruff formatting only; CI #1283 then passed formatting but failed mypy because one local variable name was reused with incompatible str and list[str] types. Both issues were corrected without expanding runtime scope.
rejected_hypotheses:
  - missing version_patch always indicates a communication failure.
  - the first two red CI runs proved a runtime scanner regression; they failed formatter/type gates before functional validation.
  - the zero-step Current HA job can be counted as PASS.
  - hardware-sensitive polling or restart-scan defaults should be changed without new physical-device measurements.
changed_paths:
  - custom_components/thessla_green_modbus/scanner/firmware.py
  - tests/test_device_scanner_firmware.py
  - docs/agents/tasks/TASK-20260811-firmware-coverage.md
validation:
  - command: GitHub Actions run 31505010765 - completed mandatory jobs and coverage
    result: PASS
    evidence: HACS, Hassfest, Lint, entity mappings, pymodbus bounds, minimum HA and Tests passed on 8eb38e7875bc554ae7aa9045c32de985924c3331; Tests job 93824694593 reports total coverage 90.82 percent and scanner/firmware.py 83 percent.
  - command: GitHub Actions run 31505638599 - complete matrix
    result: PASS
    evidence: workflow conclusion success on 8305b482de0868698338737107f7af2d397e7e6f including executed Current HA 2026.8.1 contracts.
  - command: complete GitHub Actions matrix after this ready checkpoint commit
    result: NOT_RUN
    evidence: required because this ready checkpoint changes the PR head.
blockers: []
next_action: Run the complete GitHub Actions matrix on the final ready-checkpoint head, merge PR #1767 only if every mandatory job passes, then verify the resulting main commit and post-merge CI.
```