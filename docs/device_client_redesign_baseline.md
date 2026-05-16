# DeviceClient Redesign Baseline

## Date: 2026-05-16
## Branch: claude/coordinator-deviceclient-redesign-ls3tr

## Test Results
```
2039 passed, 4 skipped, 90 warnings
```

Skipped tests:
- test_entity_data_correctness_number.py:56 - All number registers have explicit 'min'
- test_entity_data_correctness_number.py:65 - All number registers have explicit 'max'
- test_entity_data_correctness_number.py:74 - All number registers have explicit 'step'
- test_register_pdf_mapping.py:155 - could not import 'pypdf'

## Lint Results
- `ruff check custom_components tests tools` → All checks passed!
- `ruff check --select I custom_components tests tools` → All checks passed!
- `ruff format --check custom_components tests tools` → 427 files already formatted

## Tools Results
- `python tools/check_translations.py` → All translation keys present.
- `python tools/validate_entity_mappings.py` → OK: 366 entities validated
- `python tools/check_maintainability.py` → Maintainability gate passed.
- `python tools/compare_registers_with_reference.py` → Exit code 0 (242 name mismatches are pre-existing, vendor naming)

## Compile
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` → Clean

## Notes
- Python 3.13.12 in venv at /tmp/venv313
- pytest-homeassistant-custom-component 0.13.109 (Python 3.13 compatible)
- pydantic 2.12.2
