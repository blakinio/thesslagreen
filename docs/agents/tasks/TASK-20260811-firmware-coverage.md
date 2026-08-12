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
updated_at: 2026-08-12T10:03:00Z
head: 60ca43a2ad4f7b2cb594131d43eef295a5032ad4
branch: main
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
  - docs/audits/deep_audit_2026-08-11.md
proven:
  - scanner/firmware.py previously collapsed a missing version_patch to Unknown even though that register is absent on some older firmware.
  - PR #1767 preserves verified major.minor identity when patch is unavailable while missing major or minor remains an unavailable firmware condition.
  - PR #1767 does not change Modbus addresses, transport behavior, writes, entity IDs, services, or polling policy.
  - tests/test_device_scanner_firmware.py contains 8 focused tests covering unavailable firmware, full and partial fallback, partial major.minor identity, probe-error context, missing major/minor, legacy read signature fallback, serial parsing, and ASCII device-name parsing.
  - Tests job 93824694593 reported total coverage 90.82 percent and scanner/firmware.py coverage 83 percent, up from about 68 percent in the audit baseline.
  - final PR CI run 31506176043 on head ab105b57804382c595326c415de9d0cfddb23026 completed with conclusion success on rerun attempt 2.
  - PR #1767 merged to main as 60ca43a2ad4f7b2cb594131d43eef295a5032ad4.
  - post-merge CI run 31513767565 on main@60ca43a2ad4f7b2cb594131d43eef295a5032ad4 completed with conclusion success.
derived:
  - major and minor together provide useful verified firmware identity when patch is genuinely unavailable on an older unit.
  - the bounded scanner change materially improves risk-focused firmware coverage but does not by itself satisfy Home Assistant Silver per-module coverage expectations.
  - repository-local implementation and merge validation are complete; remaining acceptance is hardware/runtime evidence rather than unfinished repository work.
unknown:
  - whether a physical AirPack that lacks version_patch reports the expected major.minor value on merged main.
  - post-hardening reconnect and 24-72 hour physical soak behavior.
conflicts: []
first_failure:
  marker: candidate-ci-hygiene
  evidence: CI #1282 first failed Ruff formatting and CI #1283 then failed mypy; both were corrected without expanding runtime scope. Final CI #1286 succeeded on attempt 2 after an infrastructure-only Minimum HA installation failure in attempt 1.
rejected_hypotheses:
  - missing version_patch always indicates a communication failure.
  - early red CI runs proved a runtime scanner regression.
  - a failed dependency-install job without executed tests can be treated as a product-code failure.
  - hardware-sensitive polling or restart-scan defaults should be changed without physical-device measurements.
changed_paths:
  - custom_components/thessla_green_modbus/scanner/firmware.py
  - tests/test_device_scanner_firmware.py
  - docs/agents/tasks/TASK-20260811-firmware-coverage.md
  - docs/audits/deep_audit_2026-08-11.md
validation:
  - command: GitHub Actions run 31506176043 - final PR matrix
    result: PASS
    evidence: run attempt 2 completed successfully on exact head ab105b57804382c595326c415de9d0cfddb23026, including minimum/current HA contracts, pymodbus bounds, full Tests, Lint, Hassfest, HACS and entity mappings.
  - command: GitHub merge verification for PR #1767
    result: PASS
    evidence: PR merged as 60ca43a2ad4f7b2cb594131d43eef295a5032ad4.
  - command: GitHub Actions run 31513767565 - post-merge main CI
    result: PASS
    evidence: CI completed successfully on main@60ca43a2ad4f7b2cb594131d43eef295a5032ad4.
blockers: []
next_action: Validate merged main on the physical AirPack, confirming major.minor reporting when version_patch is absent and recording reconnect plus 24-72 hour soak evidence before polling/cache redesign.
```
