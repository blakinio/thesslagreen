# Home 400h firmware 3.11 physical acceptance

Source: manufacturer `MODBUS_USER_AirPack_Home_06.2021.01`, published as
`MODBUS_USER_AirPack_Home_08.2021.01.pdf` (17 pages). Independently extracted
334 rows / 331 unique FC/address pairs. All 331 are mapped. The repository's
26 additional definitions belong to a broader product/firmware scope.

Physical scope is the owner's standalone Home 400h, series 3 (07.2019), FW 3.11.
The owner confirms no GWC, extra duct heater/cooler or Expansion module. Reads
were executed individually both by an independent PC client and by the actual
integration transport/codecs. Mandatory RTC 0..3 and lock-date 7..9 blocks were
then read atomically. Of the 331 Home addresses, 318 respond and 13 return
explicit exceptions on this hardware; a readable reserved word does not prove
its control function exists. The full per-register/24-action evidence matrix
is retained privately with raw responses and restoration journals.

## Hardware findings fixed

- The serial block is six hexadecimal bytes, preserving leading/trailing zero
  bytes. ASCII decoding and the scanner's padded 16-bit concatenation were wrong.
  A broad info read also failed on missing firmware words; the scanner now
  independently reads the complete serial block. Device-registry identifiers
  retain the old entry/padded identifier when adding the corrected one, and the
  existing unique-id migration preserves entity IDs.
- Diagnostics respect the document's complete RTC and lock-date reads even
  with batch size one; invalid individual fallback reads are not attempted.
- `airing_switch_coef` requires FW 4.85 and `open_window_coef` requires
  3.72/4.72. Physical 3.11 reads zero and ignores valid writes. They are hidden/
  unavailable and writes are rejected before IO on incompatible firmware.
- UART configuration now checks all requested registers before writing anything.
  The previous action acknowledged unsupported settings without establishing
  that they were applicable.
- Home 3.11 echoes direct FC06/4208=2 without entering temporary mode. The writer
  now reads the current temporary target, activates atomic 4400..4402 and verifies
  effective mode 2, without guessing a percentage. All AUTO/manual/temporary
  transitions passed on hardware after the change.

- Live HA acceptance exposed a further migration defect: time/text/button and virtual fan/climate/alarm keys were missing from the migration lookup, and negative virtual addresses were not parsed. The corrected lookup and signed address parser preserve those entity IDs. Recovery removes only a newer duplicate in the same config entry when an existing older entity has the historical double-prefix defect. Final live HA and persisted registry both contain exactly the original 344 entity IDs, with no added or missing IDs and the same device ID. The correct serial is present. Original fan control reports 80/80 percent, flows 264/262 cubic metres per hour, no active alarms, stop code zero and access level zero. Global logging and device refresh actions also succeeded in real HA.

## Acceptance boundary

All 56 seasonal/day/period schedule execution cases passed on physical hardware. Each selected controller weekday, period and requested airflow matched the fixture. The initial clock restoration weekday required a separate correction; FC04 weekday 2 was subsequently verified. All 15 timed airing cases (14 weekly and one manual) also passed: full RTC date/time, a unique trigger hour per weekday, observed idle before the trigger, and resulting airing mode/100 percent were verified. The ordinary schedule weekday may refer to the previous calendar day before its first slot; it is not the airing RTC weekday. Every schedule start and settings word (56 + 56) and every seasonal airing day
(7 + 7) was changed/read/restored individually. Clock actions and an eight-word
name change were tested with restoration. Ordinary parameter storage and fan
70/80/off/on behavior were tested using the actual production handlers, fan
entity, coordinator and transport; the standalone HA registry boundary and
post-action polling were supplied by the harness. This is distinguished from
end-to-end HA verification, and from physical execution of a schedule.

Factory/schedule resets, credentials, airflow calibration and fault injection
were not performed on the working unit. Absent accessories cannot have physical
functional acceptance. Therefore full acceptance of every vendor write command
is **not claimed**, even if repository CI and normal operating tests pass.

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-10-28T12:32:20.736076+01:00
head: 4e7c0c006f316d1735bdd4cbd79646d991073559
branch: codex/fix-home-311-filter-ack
pr: https://github.com/blakinio/thesslagreen/pull/1807
status: validating
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/tasks/TASK-20261027-home-filter-alarm-reset.md
owned_paths:
  - custom_components/thessla_green_modbus/_setup.py
  - custom_components/thessla_green_modbus/capability_rules.py
  - custom_components/thessla_green_modbus/coordinator/schedule.py
  - custom_components/thessla_green_modbus/core/register_processing.py
  - custom_components/thessla_green_modbus/number.py
  - custom_components/thessla_green_modbus/registers/register_def.py
  - custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json
  - custom_components/thessla_green_modbus/scanner/firmware.py
  - custom_components/thessla_green_modbus/services/handlers_data.py
  - custom_components/thessla_green_modbus/services/handlers_maintenance.py
  - custom_components/thessla_green_modbus/entity_lookup.py
  - custom_components/thessla_green_modbus/unique_id_migration.py
  - tests/test_home_hardware_acceptance_guards.py
proven:
  - All 331 unique manufacturer FC/address pairs exist in the integration map.
  - Hardware read coverage is 318 responding Home addresses and 13 explicit firmware/equipment exceptions.
  - Every 56 schedule and 56 setting word and 14 weekly airing words passed reversible storage tests.
  - All 56 timed seasonal/day/period execution cases passed, followed by restoration and weekday correction verification.
  - All 15 timed airing cases passed with complete RTC and observed idle-to-airing transitions.
  - Live HA and persisted registry preserve all original 344 entity IDs and the device ID.
  - Six-byte serial read and full scanner identity now agree with the physical nameplate.
  - Firmware-gated reserved controls ignored documented writes; guarded before IO after repair.
  - Actual fan transitions and 70/80/off/on tests passed; final requested control is 80 percent.
  - Complete RTC sync actions and device-name write passed physical read/restore checks.
  - Latest full local suite passed 3524 tests with 3 skips; per-module coverage gates pass.
derived:
  - A successful Modbus write echo is insufficient evidence of functional support.
unknown:
  - Physical behavior of destructive/service/calibration actions not exercised on this installation.
conflicts:
  - FW 3.11 does not apply a direct documented mode-2 write; atomic activation is required.
first_failure:
  marker: physical-serial-decoder
  evidence: Six byte-valued registers were decoded as ASCII; full scanner also missed the block after optional-info failure.
rejected_hypotheses:
  - Passing unit tests proves every hardware register/function works.
  - Reading a reserved register proves its write command is functional.
changed_paths:
  - custom_components/thessla_green_modbus/_setup.py
  - custom_components/thessla_green_modbus/capability_rules.py
  - custom_components/thessla_green_modbus/coordinator/schedule.py
  - custom_components/thessla_green_modbus/core/register_processing.py
  - custom_components/thessla_green_modbus/number.py
  - custom_components/thessla_green_modbus/registers/register_def.py
  - custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json
  - custom_components/thessla_green_modbus/scanner/firmware.py
  - custom_components/thessla_green_modbus/services/handlers_data.py
  - custom_components/thessla_green_modbus/services/handlers_maintenance.py
  - custom_components/thessla_green_modbus/entity_lookup.py
  - custom_components/thessla_green_modbus/unique_id_migration.py
  - tests/test_home_hardware_acceptance_guards.py
validation:
  - command: pytest tests/ --cov
    result: PASS
    evidence: 3524 passed, 3 skipped; 98.40 percent total coverage and per-module gates pass.
  - command: ruff; mypy; reference/translation/mapping and maintainability checks
    result: PASS
    evidence: Local CI-equivalent checks.
blockers:
  - Destructive resets, credentials, calibration and fault injection deliberately not exercised on a working installation.
next_action: Review the draft PR and the explicit unsupported or untested command boundaries; no further hardware mutation is needed.
```


