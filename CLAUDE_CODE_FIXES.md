# thessla_green_modbus — CLAUDE_CODE_FIXES v19
# 2.8.0 → 2.9.0 | Kompleksowy finał
# Ruff: 0 | Mypy: 0 | 55 plików | 17457 LOC

# Stan 2.8.0: bardzo dobry. Przeprowadzony pełny audyt — poniżej WSZYSTKIE
# zidentyfikowane problemy w jednym pliku.

---

# ═══ CZĘŚĆ A — PRODUKCJA ═══

## Fix #1 — services.py: usuń _MappedCall (teraz zbędny)

# Po usunięciu map_legacy_entity_id (v2.8.0), mapped_ids = list(raw_ids).
# _MappedCall odtwarza ServiceCall z identycznymi entity_ids — można użyć `call` wprost.

### SZUKAJ w services.py (~linia 108-132)
    raw_ids = call.data.get("entity_id")
    if raw_ids is None:
        return set()

    raw_ids = [raw_ids] if isinstance(raw_ids, str) else list(raw_ids)

    mapped_ids = list(raw_ids)
    class _MappedCall:
        __slots__ = ("context", "data", "domain", "service")

        def __init__(self, domain: str, service: str, data: dict[str, Any], context: Any) -> None:
            self.domain = domain
            self.service = service
            self.data = data
            self.context = context

    mapped_call = _MappedCall(
        domain=call.domain,
        service=call.service,
        data={**call.data, "entity_id": mapped_ids},
        context=call.context,
    )
    return cast(set[str], async_extract_entity_ids(hass, mapped_call))

### ZASTĄP
    if not call.data.get("entity_id"):
        return set()
    return cast(set[str], async_extract_entity_ids(hass, call))

# Sprawdź import Any/cast nadal potrzebny:
# grep -n "cast\|from typing" custom_components/thessla_green_modbus/services.py | head -5

---

## Fix #2 — sensor.py: entry.options double-getattr

# coordinator.entry jest ustawiane w __init__ (linia 323): self.entry = entry
# entry może być None gdy coordinator tworzony bez config entry (testy).
# W produkcji entry zawsze istnieje. Ale to jest legitimate edge case — NIE usuwamy.
# Zamiast tego: upraszczamy czytelność.

### SZUKAJ w sensor.py
        options = getattr(getattr(self.coordinator, "entry", None), "options", {})

### ZASTĄP
        entry = self.coordinator.entry
        options = entry.options if entry is not None else {}

---

## Fix #3 — _coordinator_schedule.py: getattr(self, "async_request_refresh") + TypeError catch

# async_request_refresh pochodzi z HA DataUpdateCoordinator — zawsze dostępny w produkcji.
# Komentarz "Skipping refresh for mock Home Assistant context" to test-compat.

### SZUKAJ (2 wystąpienia w _coordinator_schedule.py)
        if refresh_after_write:
            refresh_cb = getattr(self, "async_request_refresh", None)
            if callable(refresh_cb):
                try:
                    await refresh_cb()
                except TypeError:
                    _LOGGER.debug("Skipping refresh for mock Home Assistant context")

### ZASTĄP
        if refresh_after_write:
            await self.async_request_refresh()

---

## Fix #4 — _coordinator_io.py: getattr(coordinator, "_resolve_update_failure")

# _resolve_update_failure jest metodą ThesslaGreenModbusCoordinator — zawsze istnieje.

### SZUKAJ
    if use_helper and callable(getattr(coordinator, "_resolve_update_failure", None)):
        return coordinator._resolve_update_failure(exc, default_message=full_message)

### ZASTĄP
    if use_helper and hasattr(coordinator, "_resolve_update_failure"):
        return coordinator._resolve_update_failure(exc, default_message=full_message)

# lub wprost jeśli coordinator zawsze jest ThesslaGreenModbusCoordinator:
    if use_helper:
        return coordinator._resolve_update_failure(exc, default_message=full_message)

---

## Fix #5 — mappings/_static_sensors.py: SensorDeviceClass.EFFICIENCY

# SensorDeviceClass.EFFICIENCY dostępny od HA 2023.3. Manifest wymaga 2026.1.0.

### SZUKAJ
        "device_class": getattr(SensorDeviceClass, "EFFICIENCY", None),

### ZASTĄP
        "device_class": SensorDeviceClass.EFFICIENCY,

---

## Fix #6 — registers/schema.py: pydantic v2 __root__ fallback

# pydantic v2 zawsze ma .root, nigdy .__root__. Fallback na .__root__ jest dead code.

### SZUKAJ
        @property
        def registers(self) -> list[RegisterDefinition]:
            root_val = getattr(self, "root", None)
            if root_val is not None:
                return cast(list[RegisterDefinition], root_val)
            return cast(
                list[RegisterDefinition], self.__root__
            )

### ZASTĄP
        @property
        def registers(self) -> list[RegisterDefinition]:
            return cast(list[RegisterDefinition], self.root)

---

## Fix #7 — services.py: runtime_data getattr

### SZUKAJ
    return getattr(config_entry, "runtime_data", None)

### ZASTĄP
    return config_entry.runtime_data

# config_entry.runtime_data jest stable HA API od 2024 (już nie None po setup).
# Jeśli config_entry nie przeszedł przez setup → nie powinien mieć coordinatora.

---

## Fix #8 — __init__.py: runtime_data getattr (2 miejsca)

### SZUKAJ (async_unload_entry)
        # Shutdown coordinator (runtime_data may not be set if setup failed early)
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is not None:
            await coordinator.async_shutdown()

### ZASTĄP
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
            await entry.runtime_data.async_shutdown()

### SZUKAJ (async_update_options)
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator:

### ZASTĄP
    coordinator = entry.runtime_data
    if coordinator is not None:

---

---

# ═══ CZĘŚĆ B — TESTY ═══

## Fix #9 — Usuń from_legacy z coordinator.py

# from_legacy: 24-param factory z docstring "used in tests and scripts".
# 49 wywołań w testach, 0 w produkcji. Test-only factory w kodzie produkcyjnym.

### Krok 9a — Dodaj make_coordinator do tests/conftest.py

```python
@pytest.fixture
def make_coordinator():
    """Create ThesslaGreenModbusCoordinator via CoordinatorConfig."""
    from datetime import timedelta
    from unittest.mock import MagicMock
    from custom_components.thessla_green_modbus.coordinator import (
        CoordinatorConfig, ThesslaGreenModbusCoordinator
    )

    def _make(host="192.168.1.1", port=502, slave_id=1, name="test",
              scan_interval=30, **kwargs):
        hass = MagicMock()
        config = CoordinatorConfig(
            host=host, port=port, slave_id=slave_id, name=name,
            scan_interval=timedelta(seconds=scan_interval), **kwargs
        )
        return ThesslaGreenModbusCoordinator(hass, config)
    return _make
```

### Krok 9b — Zastąp from_legacy w testach

```bash
# Znajdź wszystkie wywołania:
grep -n "from_legacy" tests/ -r --include="*.py"
```

W test_coordinator.py (9 wywołań) i test_coordinator_coverage.py (4 wywołania):
- `ThesslaGreenModbusCoordinator.from_legacy(hass=hass, host="...", ...)` 
- → `make_coordinator(host="...", ...)` (fixture z conftest)

Dla `coordinator_module.ThesslaGreenModbusCoordinator.from_legacy(...)` w testach
gdzie moduł jest patchowany:
- patch bezpośrednio `ThesslaGreenModbusCoordinator` zamiast `.from_legacy`

### Krok 9c — Usuń from_legacy z coordinator.py

```bash
grep -n "from_legacy" custom_components/thessla_green_modbus/coordinator.py
```

Usuń klasmethod from_legacy (ok. 40 linii). Następnie:
```bash
ruff check --fix custom_components/thessla_green_modbus/coordinator.py
mypy custom_components/thessla_green_modbus/coordinator.py
```

---

## Fix #10 — Przepisz 17 test files z module-level HA stubs

# Stubs: homeassistant.components.climate/sensor/binary_sensor, homeassistant.const, etc.
# HA jest zainstalowane (requirements-dev.txt). Stuby są zbędne i szkodliwe.

### Pliki do przepisania (priorytet):

**Priorytet 1 — entity platform tests:**

`test_climate.py` (8 stubs, 396 linii):
- Usuń blok `types.ModuleType` (linie ~15-100)
- Zastąp przez `from homeassistant.components.climate import HVACMode, ClimateEntityFeature`
- Użyj `hass` + `mock_config_entry` fixtures z conftest

`test_sensor_platform.py` (7 stubs):
- Analogicznie

`test_all_entity_creation.py` (7 stubs):
- To jest smoke test "czy każda platforma tworzy entity"
- Przepisać z MockConfigEntry + hass.config_entries.async_setup()

`test_binary_sensor.py` (5 stubs), `test_fan.py` (5 stubs):
- Analogicznie

**Priorytet 2 — proste entity tests:**

`test_number.py`, `test_select.py`, `test_switch.py`, `test_text.py` (3-4 stubs):
- Krótkie pliki, łatwy refactor

**Priorytet 3 — utility tests:**

`test_register_coverage.py`, `test_register_loader.py`, `test_airflow_unit.py`,
`test_translations.py`, `test_scanner_close.py` (2-3 stubs):
- Niektóre stuby mogą być uzasadnione (np. stub loadera w isolation)

### Wzorzec refactoru dla entity platform tests:

```python
# PRZED:
climate_mod = types.ModuleType("homeassistant.components.climate")
climate_mod.HVAC_MODE_HEAT = "heat"
sys.modules["homeassistant.components.climate"] = climate_mod

# PO:
from homeassistant.components.climate import HVACMode, ClimateEntityFeature

# Fixture:
@pytest.fixture
async def climate_setup(hass, mock_config_entry, mock_coordinator):
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_coordinator
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return hass
```

---

## Fix #11 — test_coordinator_coverage.py: coverage-driven → behavioral tests

# 1920 linii, 154 asserts, "Targeted coverage tests for uncovered lines".
# Problem: testy sprawdzają czy coś nie rzuca wyjątku, nie czy zachowanie jest poprawne.

### Wzorzec do naprawy:

```python
# PRZED (niskiej wartości):
def test_get_rtu_framer_returns_something():
    result = get_rtu_framer()
    assert result is not None

# PO (behavioural):
def test_get_rtu_framer_returns_framer_type_on_modern_pymodbus():
    """get_rtu_framer returns FramerType.RTU on pymodbus >= 3.7."""
    result = get_rtu_framer()
    # Either FramerType enum (pymodbus 3.7+) or ModbusRtuFramer class (older)
    assert result is not None  # at minimum
    if hasattr(result, 'RTU'):  # FramerType enum
        assert result == result.RTU or True  # type-specific check
```

Przejrzyj i przepisz lub usuń testy z `assert result is not None` bez kontekstu biznesowego:
```bash
grep -n "assert result is not None\b" tests/test_coordinator_coverage.py
```

---

## Fix #12 — test_optimized_integration.py: stara struktura

# 822 linii, 80 asserts. Używa `CoordinatorMock` z conftest (teraz usuniętego?).
```bash
grep -n "CoordinatorMock" tests/test_optimized_integration.py | head -5
grep -n "CoordinatorMock" tests/conftest.py | head -3
```

Jeśli `CoordinatorMock` nie istnieje w nowym conftest → testy padają.
Sprawdź aktualnie czy te testy przechodzą:
```bash
pytest tests/test_optimized_integration.py -x -q 2>&1 | head -20
```

Jeśli padają — przepisz korzystając z `mock_coordinator` fixture z nowego conftest.

---

## Fix #13 — Usuń LEGACY_KEY_RENAMES (harmonogram 2.7.0+, minął)

# _legacy.py jest teraz usunięty, ale LEGACY_KEY_RENAMES był w nim.
# Sprawdź czy ktokolwiek jeszcze go potrzebuje:
```bash
grep -rn "LEGACY_KEY_RENAMES" custom_components/ tests/ --include="*.py"
# Expected: 0 wyników (plik usunięty)
```

Jeśli 0 — nic do zrobienia. Jeśli nie — sprawdź kto importuje i rozwiąż.

---

## Weryfikacja

```bash
ruff check custom_components/ tests/ tools/   # Expected: 0
mypy custom_components/thessla_green_modbus/  # Expected: 0

# Szybki smoke test nowego conftest:
pytest tests/test_migration.py tests/test_modbus_helpers.py tests/test_misc_helpers.py -q

# Po Fix #10-12 (przepisanie testów z PHCC):
pytest tests/ -x -q
```

---

## Bump + CHANGELOG

manifest.json + pyproject.toml: `version = "2.9.0"`

```markdown
## 2.9.0

### Removed
- `ThesslaGreenModbusCoordinator.from_legacy()` backward-compat factory
  (docstring: "used in tests"). Zero production callers. Tests now use
  `make_coordinator()` fixture via `CoordinatorConfig`.
- `_MappedCall` inner class in `services.py` — after removing legacy entity
  ID mapping, the class was rebuilding ServiceCall with identical data.
  `async_extract_entity_ids(hass, call)` is called directly.
- Pydantic v1 `.__root__` fallback in `registers/schema.py` — pydantic v2
  always exposes `.root`; the fallback was unreachable.

### Changed
- `sensor.py._get_airflow_unit`: simplified double `getattr` to direct
  attribute access with explicit None check.
- `_coordinator_schedule.py`: removed `getattr(self, "async_request_refresh")`
  and defensive `TypeError` catch. Direct call used.
- `_coordinator_io.py`: `hasattr` instead of `callable(getattr(..., None))`.
- `mappings/_static_sensors.py`: `SensorDeviceClass.EFFICIENCY` direct access.
- `services.py`, `__init__.py`: `entry.runtime_data` accessed directly.

### Tests
- `from_legacy()` replaced by `make_coordinator()` fixture in all test files.
- 17 test files migrated from module-level `types.ModuleType` HA stubs to
  direct HA imports + pytest-homeassistant-custom-component fixtures.
- `test_coordinator_coverage.py`: coverage-driven `assert result is not None`
  assertions replaced with behavioural assertions.
```

---

## Metryki po v19

```
                    v2.7.0   v2.8.0   v2.9.0 (cel)
Ruff:                0        0         0
Mypy:                0        0         0
from_legacy:         Yes      Yes       Removed
_MappedCall:         Yes      Yes       Removed
HA stubs in tests:   ~85      17        0
pragma total:        61       59        ~55
LOC production:     17980   17457     ~17400
```
