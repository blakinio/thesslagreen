---
task_id: TASK-20260811-firmware-coverage
status: validating
owner: codex
scope: improve firmware identity semantics and scanner coverage without changing Modbus transport contracts
---

# Firmware identity and coverage hardening

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-11T15:10:00Z
head: 8eb38e7875bc554ae7aa9045c32de985924c3331
branch: feat/firmware-coverage-20260811
pr: 1767
status: validating
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
  - CI run 31505010765 on head 8eb38e7875bc554ae7aa9045c32de985924c3331 passed HACS, Hassfest, Lint including mypy/checkpoint validation, entity mappings, pymodbus 3.6.1, pymodbus 3.14.0, minimum HA 2026.1.0, and the full Tests job.
  - Tests job 93824694593 completed successfully with total coverage 90.82 percent and scanner/firmware.py coverage 83 percent, up from about 68 percent in the prior audit baseline.
  - the Current HA 2026.8.1 job 93824694371 in run 31505010765 is stuck in GitHub as in_progress with a runner assigned but zero steps and no downloadable log.
derived:
  - major and minor together provide useful verified firmware identity when patch is genuinely unavailable on an older unit.
  - the bounded scanner change materially improves risk-focused firmware coverage but does not by itself satisfy Home Assistant Silver per-module coverage expectations.
  - the zero-step Current HA job state is runner/workflow infrastructure evidence, not a passing or failing code result, so a fresh complete run is required.
unknown:
  - whether a fresh complete CI run passes the Current HA 2026.8.1 contract job on the final candidate.
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
  - command: GitHub Actions run 31505010765 - HACS, Hassfest, Lint, entity mappings, pymodbus bounds, minimum HA and Tests
    result: PASS
    evidence: all listed jobs completed successfully on head 8eb38e7875bc554ae7aa9045c32de985924c3331; Tests job 93824694593 reports total coverage 90.82 percent and scanner/firmware.py 83 percent.
  - command: GitHub Actions run 31505010765 - Current HA API contracts 2026.8.1
    result: NOT_RUN
    evidence: job 93824694371 remains in_progress with zero steps and no log, so it cannot be treated as executed evidence.
  - command: fresh complete GitHub Actions matrix after this checkpoint commit
    result: NOT_RUN
    evidence: required to replace the unusable zero-step Current HA job with exact final-head evidence.
blockers: []
next_action: Run the complete GitHub Actions matrix on the checkpointed candidate, fix only evidenced failures, mark ready only after every mandatory job including Current HA 2026.8.1 passes, then merge PR #1767 and verify post-merge main CI.
```