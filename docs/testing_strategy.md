# Testing Strategy

## Target test structure
```text
tests/
├── conftest.py
├── unit/
├── transport/
├── scanner/
├── core/
├── coordinator/
├── ha/
├── platforms/
└── services/
```

## Tier 1 — pure unit
- bez HA,
- bez pymodbus,
- bez sieci.

Zakres: registers, codec, read planner, retry classification, errors, constants.

## Tier 2 — mock transport / mock pymodbus
- transport,
- scanner,
- core client,
- coordinator z mockowanym clientem.

## Tier 3 — real HA / PHCC
- setup/unload/reload,
- config flow,
- options flow,
- reauth flow,
- platforms,
- diagnostics,
- services,
- entity unique_id,
- unavailable state.

## Zakazy
- brak `platform_stubs.py`,
- brak `sys.modules` patchowania Home Assistant,
- brak testów coverage-driven,
- brak `assert result is not None` bez znaczenia biznesowego.

## Przykłady dobrych nazw testów
```python
test_marks_entities_unavailable_when_device_times_out()
test_reuses_scan_cache_when_device_scan_is_disabled()
test_skips_unsupported_register_after_illegal_address()
test_raises_service_validation_error_for_unknown_register()
test_creates_only_supported_entities_after_scan()
```
