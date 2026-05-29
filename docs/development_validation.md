# Development Validation Guide

This document describes how to reproduce the full CI validation locally.

---

## Required Python version

**Python 3.13 is required.**

Home Assistant's test stack (`pytest-homeassistant-custom-component`) has a hard
dependency on Python 3.13. Running with Python 3.11 or 3.12 is not sufficient —
import errors or silent test collection failures will occur.

Python 3.11 or 3.12 sandboxes (including some agent/CI environments) are
**not authoritative** for full pytest results. If your local environment provides
only Python 3.11, rely on the GitHub Actions CI job for full pytest results.

---

## Setup

### With uv (recommended)

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements-dev.txt
uv pip install -e .
uv pip install "homeassistant==2026.2.3"
```

### With standard venv

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
pip install "homeassistant==2026.2.3"
```

---

## Full validation command block

Run these commands in order from the repository root. All must pass before merging.

```bash
python -m compileall -q custom_components/thessla_green_modbus tests tools
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
python tools/compare_registers_with_reference.py --show-renames
python tools/compare_airpack4_vendor_coverage.py
python tools/validate_entity_mappings.py
python tools/check_translations.py
python tools/check_maintainability.py
pytest --collect-only -q
pytest tests/ -q --tb=long
```

---

## Focused test command block

Run these when working on a specific area to get faster feedback:

```bash
# Core areas from recent PRs
pytest -q tests/ -k "coordinator or device_client or fan or dangerous or entity_category or register_map or orchestration or maintainability" --tb=long

# Fan percentage
pytest -q tests/test_fan.py tests/test_fan_percentage_limits.py --tb=long

# Dangerous entities
pytest -q tests/test_airpack4_dangerous_entity_marking.py tests/test_airpack4_dangerous_register_exposure.py --tb=long

# IO ownership
pytest -q tests/test_coordinator_io_ownership.py --tb=long

# Cleanup/pin checks
pytest -q tests/test_cleanup_audit.py --tb=long
```

---

## CI environment

The GitHub Actions CI (`CI` workflow) mirrors the full validation block above.
It runs on:

- **Python:** 3.13
- **Home Assistant:** 2026.2.3
- **Trigger:** push to `main`, all pull requests, manual `workflow_dispatch`

Jobs:

| Job | What it checks |
|-----|---------------|
| `lint` | ruff lint, ruff import-order, ruff format, compileall, register comparison, airpack4 coverage, translations, maintainability |
| `tests` | pytest collect + full pytest with coverage |
| `entity-mappings` | entity mapping validation |
| `hassfest` | HA manifest validation |
| `hacs` | HACS integration validation |

---

## Notes

- **Python 3.11 is not sufficient.** The `pytest-homeassistant-custom-component`
  fixture stack imports HA internals that require Python 3.13.
- **Agent/sandbox environments** that report Python 3.11 cannot confirm full
  pytest results. State the Python version explicitly in any PR description and
  note which checks were run locally vs deferred to CI.
- **pymodbus must remain `>=3.6.0,<4.0`** in both `manifest.json` and
  `pyproject.toml`. The pymodbus 4.x migration is documented in
  `docs/pymodbus_4_migration_plan.md` but is not active.
- **Do not upgrade `quality_scale`** from `bronze` until real-device validation
  evidence is committed. See `docs/real_device_validation.md`.
