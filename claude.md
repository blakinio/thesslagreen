# CLAUDE.md — Agent guidelines for thessla_green_modbus

This file is read automatically by Claude Code at the start of every session in this repo.
It defines the rules, environment, validation, and reporting expected for ALL tasks.
Per-task prompts may reference this file with: "Follow the guidelines in CLAUDE.md."

This is a Home Assistant custom integration for ThesslaGreen AirPack4 HVAC units over Modbus.
Architecture is layered: `transport → core → coordinator → platforms`.

---

## 1. Hard Rules (violating any one is a failed task)

- **Branch:** work on `main`. Never use, create, or reintroduce `dev`.
- **Never change public contracts:** Modbus register addresses, register names, entity IDs,
  unique IDs, service IDs, translation keys. These break existing user installations.
- **Never change** config/options flow behavior unless the task explicitly requires it.
- **No compatibility shims / re-export modules.** Update all import sites directly.
  See `docs/thesslagreen_guidelines.md`.
- **Do not reintroduce** `modbus_helpers.py` (it was deliberately removed).
- **No broad refactor** unless the task is explicitly labeled a refactor task.
- **Preserve layer isolation:** `transport/`, `core/`, `scanner/`, `registers/`, `modbus/`
  must NOT import `homeassistant` (except under `TYPE_CHECKING`) and must NOT import from
  `coordinator/` or platform modules. `tests/test_dependency_direction.py` enforces this —
  never weaken it; you may strengthen it.
- **Keep `core/client.py` as the mixin assembler.** Do not merge it into a monolith.
  Small helper modules may be consolidated into their sole caller only when the matching
  plan document explicitly allows that slice.
- **Do not touch** the batch boundaries `{16, 8192}` in `const.py` — these encode AirPack4
  firmware constraints, not magic numbers.
- **Do not raise `quality_scale` above `bronze`** until `docs/real_device_validation.md`
  is marked PASS with committed evidence from a real device.
- **Zero behavior change** in refactor tasks — moves and delegation only, never logic edits.

---

## 2. Environment

- **Python 3.13 is required** (`requires-python = ">=3.13"`). The test stack
  (`pytest-homeassistant-custom-component`) has a hard 3.13 dependency.
- If `pytest` cannot collect in your sandbox (e.g. it runs 3.11/3.12), run `compileall`,
  `ruff`, and the `tools/` validators instead, and **explicitly flag** in the report that
  full pytest needs CI verification on Python 3.13.
- **Never modify tests** just to make them collect on an older Python.
- Lightweight validators (`tools/validate_*.py`) only need `pydantic`, `PyYAML`,
  `voluptuous` (see `requirements-test-min.txt`) and run without the full HA stack.

---

## 3. Investigate before assuming

- **grep for a mechanism before concluding it does not exist.** Example: before saying there
  is no refresh-suppression / concurrency guard, search for `_update_in_progress`,
  `_client_lock`, `_write_lock`.
- **grep all call sites before changing** a function's return value or exception contract,
  and confirm every caller handles the new contract.
- Read the relevant `docs/*_plan.md` in full before executing a planned refactor — those
  documents are the source of truth.

---

## 4. Real-device safety

- Prefer `validate_known_registers` for real-device validation.
- Do not use broad `scan_all_registers` as routine validation.
- If touching `scan_all_registers`, preserve read-only behavior and warn that it opens a
  separate Modbus connection.
- Treat Modbus exception code 2 as an unsupported register/range, not as a fatal device
  failure.
- Never add unknown registers as entities automatically.
- Do not change Modbus register addresses/names or entity/service IDs based on unknown scan
  output.

---

## 5. Validation (run all that apply; if pytest is unavailable, run the rest and flag it)

```bash
python -m compileall -q custom_components/thessla_green_modbus tests tools
pytest --collect-only -q
pytest tests/ -q --tb=long
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
python tools/compare_registers_with_reference.py --show-renames
python tools/compare_airpack4_vendor_coverage.py
python tools/check_maintainability.py
python tools/validate_entity_mappings.py
python tools/check_translations.py
```

All applicable commands must pass before a task is considered done.

---

## 6. Report format (required for every task)

- **Files changed** — added / modified / deleted (use `git mv` for moves to preserve history).
- **Root cause** per fix (1–2 sentences each).
- **Call sites inspected** whenever a signature, return value, or exception contract changed.
- **Tests added** — file + what each one asserts.
- **Validation output** — which commands passed; flag pytest if Python < 3.13.
- **Rules self-audit** — explicitly confirm that NO register addresses/names, entity IDs,
  unique IDs, service IDs, or translation keys were changed.
- **Remaining risks** and any follow-up issues (document in `docs/` if structural).

---

## 7. Changelog policy

Update `CHANGELOG.md` (root) on **every PR** that touches runtime code, entity
behavior, services, register mappings, entity/unique/service IDs, diagnostics, or
any structural refactor.

Place entries under the appropriate subsection of `[Unreleased]`:

| Subsection | When to use |
|---|---|
| `Added` | New feature, entity, service, or capability |
| `Changed` | Behavioral change, renamed display name, recategorised entity |
| `Fixed` | Bug fix, incorrect state, wrong log message |
| `Removed` | Deleted entity, service, register, or module |
| `Docs` | Documentation or real-device evidence committed |
| `Internal` | Refactor, test-only change, tooling, CI |

PRs that are **test-only, docs-only, or internal-only** may omit a CHANGELOG entry
provided the PR body contains: `No changelog: <reason>`.

Do **not** claim release status (version tag, "shipped") unless a GitHub release
already exists for that version.

---

## 8. Refactor tasks — additional rules

Apply these only when the task is explicitly a refactor/migration:

- **One concern per slice**, and **one slice per commit**. Run full validation after each.
- **Use `git mv`** for file moves — never copy-paste (preserves history).
- **Verify no circular imports** with `compileall` after every move.
- **Update the matching plan doc** after each slice (mark DONE, add "what was done" +
  rollback plan), e.g. `docs/core_consolidation_plan.md`,
  `docs/coordinator_proxy_remaining_plan.md`.
- **Respect "runtime-required" classifications** in the plan docs — do not remove proxies
  or helpers marked as required.
- **Blocked slices:** report explicitly with the reason and stop. Never force a slice whose
  preconditions (e.g. real-device validation PASS, a prior slice being stable) are unmet.

---

## 9. Key reference docs

- `docs/thesslagreen_architecture.md` — layer design and rationale.
- `docs/thesslagreen_guidelines.md` — coding guidelines (incl. no-shim rule).
- `docs/coordinator_proxy_remaining_plan.md` — coordinator proxy reduction plan + counts.
- `docs/core_consolidation_plan.md` — core/ consolidation slices + rules.
- `docs/pymodbus_4_migration_plan.md` — pymodbus 4.0 migration plan (pin is `<4.0`).
- `docs/real_device_validation.md` — real-device validation status (gates the quality scale).
- `docs/development_validation.md` — how to reproduce CI locally.
