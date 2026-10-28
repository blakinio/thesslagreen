# Home 3.11 filter acknowledgement and fan control

The physical Home 3.11 controller cleared active S17 (8209) and E252 (8444)
after writing 1 to each flag; successful readback is 0. Writing 0 did not
clear them. The vendor table describes binary states, not this command
semantic. The write-one result is hardware evidence for firmware 3.11.

The new reset action requires physical replacement confirmation, Home family
and one target. It skips inactive flags, verifies zero after acknowledging an
active flag and preserves filter configuration. Other firmware retains the
zero command path and is not physically verified here. Diagnostics only read.

AUTO and temporary fan commands now use the existing atomic 4400-4402 writer
instead of the absent temporary_2 alias. Validation requires the complete
block. Missing power control in AUTO/temporary mode fails explicitly.

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-10-28T08:45:00+00:00
head: b9495952b4ad20dfa82c5b661879465d98e64f5c
branch: codex/fix-home-311-filter-ack
pr: https://github.com/blakinio/thesslagreen/pull/1807
status: ready
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
owned_paths:
  - custom_components/thessla_green_modbus/fan.py
  - custom_components/thessla_green_modbus/services/handlers_filter_alarms.py
  - custom_components/thessla_green_modbus/services/__init__.py
  - custom_components/thessla_green_modbus/services.yaml
  - custom_components/thessla_green_modbus/strings.json
  - custom_components/thessla_green_modbus/translations/en.json
  - custom_components/thessla_green_modbus/translations/pl.json
  - tests/conftest.py
  - tests/test_fan.py
  - tests/test_quality_scale_fan_remaining.py
  - tests/test_home_filter_alarm_ack.py
proven:
  - Physical Home 3.11 cleared S17 and E252 after single-register writes of 1.
  - Both flags and stop code are zero; filter system remains presostat type 1.
  - Physical fans reached 80 and 80; HA shows nonzero flows and no active alarms.
  - Integration enabled after installation and restart; reset action succeeds for inactive flags.
  - AUTO HA helper disabled to preserve the owner's explicit 80 percent request.
  - Full suite passed 3379 tests with 3 skips; all per-module coverage targets passed.
  - Ruff, mypy, translations, register reference, vendor coverage and entity mappings pass.
derived:
  - Acknowledgement command value differs from resulting state on Home 3.11.
unknown:
  - Physical acknowledgement behavior on other firmware versions.
conflicts:
  - Earlier zero writes failed; replaced by hardware-verified write-one handling for 3.11.
first_failure:
  marker: obsolete-temporary-alias
  evidence: AUTO validation required an alias absent from the actual register map.
rejected_hypotheses:
  - Service access or disabling pressure protection is necessary for this reset on 3.11.
changed_paths:
  - custom_components/thessla_green_modbus/fan.py
  - custom_components/thessla_green_modbus/services/handlers_filter_alarms.py
  - custom_components/thessla_green_modbus/services/__init__.py
  - custom_components/thessla_green_modbus/services.yaml
  - custom_components/thessla_green_modbus/strings.json
  - custom_components/thessla_green_modbus/translations/en.json
  - custom_components/thessla_green_modbus/translations/pl.json
  - tests/conftest.py
  - tests/test_fan.py
  - tests/test_quality_scale_fan_remaining.py
  - tests/test_home_filter_alarm_ack.py
validation:
  - command: pytest tests/ --cov
    result: PASS
    evidence: 3379 passed, 3 skipped; Python 3.13.18 and HA 2026.2.3; 98.38 percent coverage.
  - command: ruff check and format; mypy; vendor and translation checks
    result: PASS
    evidence: Local CI-equivalent checks.
blockers:
  - No hardware or local validation blocker; remote CI pending.
next_action: Inspect PR 1807 CI results for the current head; keep the PR in draft until reviewed.
```


