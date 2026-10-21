# AirPack Home / AirPack4 protocol corrections

## Scope and source identity

Candidate extends draft PR #1773 at `4990677c9826765aad5d80afe6d5d72c61765efb`.
Public main was independently checked at `b198c626d20797978bb78dbbab1fe2934fc1dc32`.
No unrelated dependency PR, workflow, firmware or version bump is included.
The owner identifies the installed unit as AirPack Home 400h Energy; this is not
inferred from nominal airflow or the availability of optional registers.

Manufacturer contracts were taken from the owner's supplied PDFs:

- Home: internal revision `MODBUS_USER_AirPack_Home_06.2021.01`
  (supplied filename ends `08.2021.01.pdf`).
- AirPack4: `MODBUS_USER_AirPack_4_08.2022.01`.

The PDFs are not committed or republished here. Page references below identify
source contracts, not post-fix physical acceptance.

## Root causes, corrections and call sites

| Area | Source and root cause | Implementation and checked callers |
| --- | --- | --- |
| Special functions | Both PDFs p.11: FC03/4224 is a vendor enum, not ordered lifestyle presets. | `registers/special_modes.py`, `const.py`, parser, select, climate, switch and all three mode-service aliases share vendor values. Switch identity suffixes are retained separately from command values. |
| Season | Both PDFs p.11: FC03/4209 is summer=0, winter=1. | Correct static select states; test both read and write semantics. |
| Schedule AATT | Both PDFs p.8-9: one word contains integer airflow and twice temperature; 20%,22 C = 0x142C. | `handlers_schedule.py`, `core/schedule_values.py`, `register_def.py`, coordinator locked read/modify/write. Updated the old tests which asserted temperature loss or double encoding. |
| Disabled times | Both PDFs p.6-7 and p.10-11: 0xA200 disables a slot; 0x2400 disables airing; midnight is 0x0000. | BCD decoder/encoder and scanner preserve presence with disabled values; new airing service and optional slot `enabled` field. |
| Writable registers | Both PDFs p.2,12-15: status/measurement registers are read-only. | Coordinator named-write resolver and raw FC16 span validation; bypass/GWC service control targets and all-parameter preflight. No new physical addresses. |
| Filters | Home p.15 selects type 1..4; non-presostat disables pressure monitoring. AP4 p.15 uses per-side 17/33 without AFC. | Explicit family option gates both named and raw filter writes. Replacement preserves Home type and rejects presostat writes; AP4 requires direction and no-AFC confirmation. |
| Pressure tests | Both PDFs p.5: configuration mode 47, or 65 for AFC plus duct filter. | Explicit procedure/equipment confirmation; do not reschedule the weekly test as a substitute. |
| Cancellation/recovery | Poll flag set before lock acquisition; HA callback returns no coroutine. | Outer `finally` clears the flag, cancellation during lock wait leaves the other owner's transport alone; reauth callback called once and only authentication errors initiate reauth. |
| Measurements/presentation | Both PDFs p.3,10: inactive CF=65535, RTC signed byte, module versions split into bytes, FPX protection is thermal. AP4 p.15 has packed filter dates. | Runtime decoder, scanner, sensor aggregation, diagnostics and display metadata; no guessed optional equipment. |

## Migration and compatibility

No register address/name, entity ID, unique ID or existing service ID is renamed.
Historical switch `bit` identity fields stay fixed; protocol values are separate.
New option/service/translation fields are additive. The quality scale remains bronze.

Corrected semantic values intentionally change behavior. Legacy Boost maps to manual
airing (7), Away to Empty House (11), Hood to 1 and Fireplace to 2. Lifestyle presets
without a documented equivalent are rejected, not silently mapped. Their switch
entities remain registered but unavailable, preserving references/history for explicit
migration. Use the canonical special-mode selector; season and comfort are separate.

Selecting a family is required only for variant-dependent filter operations. There is
no automatic filter reset, AFC detection guess, presostat deactivation, firmware change,
new hardware scan or installation step in this change. Home pressure-based filter
monitoring requires physical inspection when it alarms, not a software type reset.

The Home and AP4 PDFs contradict themselves in the description/information columns
for FC04/274-275. This candidate does not resolve that contradiction by renaming them
or silently changing energy calculations to a supposedly proven alternative.

## Validation and boundaries

Exact commands and captured results are recorded in the companion evidence JSON.
Manufacturer regression tests exercise the runtime with mocked transport boundaries,
including real encoding and the poll decoder, not just duplicated arithmetic.
Current-HA tests initialize mappings through the real setup builder and dereference
its current mapping object; this is needed when running without the upstream conftest.

Full device acceptance remains pending. A successful test suite is not evidence of
physical writes, successful restart of HA/NAS, optional hardware or alarm clearance.
The first independent Codex attempts were blocked before reading source. Three later
owner-authorized, prompt-only scoped reviews completed against commit `72ea7759` with
zero child tool calls. Their five findings were reproduced/corrected and regression
tested; see `docs/agents/evidence/home-protocol-corrections-20261021/independent-review.md`.
These scoped reviews are not full-repository approval or hardware acceptance.

## Deployment and rollback

Do not merge or deploy automatically. Keep the PR draft until exact-head CI and a
controlled real-device acceptance matrix are complete. Before installation, export
integration files/options and affected automations/dashboard references. Restore the
previous integration directory and options to roll back; do not reset controller data.
Prior work in the conversation separately changed the owner's HA watchdog and created
four helpers; that is not an integration-code deployment and is not part of this PR.
This continuation does not alter HA or issue any Modbus command.

Required physical checks after separate deployment approval: read-only startup and
freshness; loss/recovery of transport; manual-mode/temperature convergence from #1773;
safe preset/season mapping; one backed-up schedule slot with read-back and restoration.
Never exercise factory reset, product-key, calibration or filter-system changes as
routine acceptance tests.

## Reviewed follow-up

Schedule edits now serialize settings/time under one transport lock and reconcile
partial/cancelled writes. Polls recheck shutdown after waiting for the lock. Invalid
AATT words are unavailable, and both explicitly selected Home/AP4 profiles support
the documented confirmed AFC/duct procedure. No such procedure was physically run.
