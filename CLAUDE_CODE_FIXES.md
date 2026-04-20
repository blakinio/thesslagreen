# thessla_green_modbus — CLAUDE_CODE_FIXES v18
# 2.7.0 → 2.8.0 | Legacy + Test quality

---

# ═══ CZĘŚĆ 1 — LEGACY REMOVAL (z v17) ═══

## Fix #1 — Usuń zapis "unit" z nowych config entries
# Plik: config_flow.py ~752
### SZUKAJ
            "unit": self._data[CONF_SLAVE_ID],  # legacy compatibility
### USUŃ tę linię

## Fix #2 — Usuń odczyt "unit" z setup
# Plik: _setup.py ~70
### SZUKAJ
    if CONF_SLAVE_ID not in entry.data and "unit" in entry.data:
        config.slave_id = int(entry.data["unit"])
### USUŃ obie linie

## Fix #3 — Usuń "unit" fallback z _entry_migrations.py
### SZUKAJ
    elif "unit" in new_data:
        slave_id = new_data["unit"]
### USUŃ

## Fix #4 — Zatrzymaj entity migrations przy restarcie
# Plik: __init__.py linie 86-87
### SZUKAJ
    await _async_migrate_unique_ids(hass, entry)
    await _async_migrate_entity_ids(hass, entry)
### USUŃ obie linie + ich importy z nagłówka

## Fix #5 — Usuń _entity_registry_migrations.py
```bash
rm custom_components/thessla_green_modbus/_entity_registry_migrations.py
```
Zaktualizuj _migrations.py — usuń referencje do async_migrate_entity_ids i async_migrate_unique_ids.

## Fix #6 — Usuń _legacy.py (staje się dead code po Fix #5)
```bash
grep -rn "from \._legacy\|from \..*_legacy\b" custom_components/ tests/ --include="*.py"
# Jeśli tylko z _entity_registry_migrations.py (usuniętego) → bezpiecznie usunąć
rm custom_components/thessla_green_modbus/_legacy.py
```

## Fix #7 — Usuń LEGACY_ENTITY_ID_OBJECT_ALIASES i map_legacy_entity_id
# Plik: mappings/legacy.py — usuń cały dict (70 wpisów) i funkcję map_legacy_entity_id
# Plik: services.py — zastąp wywołania:
### SZUKAJ
    mapped_ids = [map_legacy_entity_id(entity_id) for entity_id in raw_ids]
### ZASTĄP
    mapped_ids = list(raw_ids)
### SZUKAJ
    mapped_entity_id = map_legacy_entity_id(entity_id)
### ZASTĄP
    mapped_entity_id = entity_id
# Usuń import z services.py. Usuń LEGACY_ENTITY_ID_ALIASES (pusty) z mappings/__init__.py.

## Fix #8 — Migracje v2/v3 → error
# Plik: _entry_migrations.py — zastąp bloki v2 i v3:
### ZASTĄP
    if config_entry.version in (2, 3):
        _LOGGER.error("Config entry version %s (pre-2023) no longer supported.", config_entry.version)
        return False
# Uruchom: ruff check --fix custom_components/thessla_green_modbus/_entry_migrations.py

## Fix #9 — Usuń scanner_io.py (0 importerów)
```bash
rm custom_components/thessla_green_modbus/scanner_io.py
```

## Fix #10 — Usuń tools/py_compile_all.py
```bash
rm tools/py_compile_all.py
```

## Testy do usunięcia (testują usunięty kod)
```bash
rm tests/test_legacy_entity_id_aliases.py
rm tests/test_legacy_entity_migration.py
rm tests/test_services_legacy_ids.py
# test_init_helpers.py — usuń testy dla extract_legacy_problem_key i extract_key_from_unique_id
# test_migration.py — zaktualizuj: v1 → False, v2/v3 → False, v4 → True
```

---

# ═══ CZĘŚĆ 2 — AUDYT JAKOŚCI TESTÓW ═══

## Problem architektoniczny — fundamentalny

Testy używają własnych stubów HA zamiast `pytest-homeassistant-custom-component`.
Efekt: **96 plików testów testuje głównie własne mocki, nie realny kod integracji z HA.**

```
pytest.ini: -p no:pytest_homeassistant_custom_component  ← WYŁĄCZONE!
conftest.py: DataUpdateCoordinator stub, ConfigEntry stub, ConfigFlow stub...
test_coordinator.py: 17 HA module stubs budowanych od zera
test_services.py: 18 HA module stubs + voluptuous stub
test_all_entity_creation.py: 19 stubs
```

Konsekwencje:
- `ThesslaGreenModbusCoordinator.super().__init__()` wywołuje STUB, nie HA
- `async_setup_entry` nigdy nie wchodzi w HA entity registry pipeline
- Testy config_flow testują ConfigFlow dziedziczący po StubClass, nie HA ConfigFlow
- 23 klasy HA monkey-patchowane w conftest → każda jest uproszczona

**To nie jest błąd testerów — to wynik historyczny, kiedy testy pisano zanim dodano pytest-homeassistant-custom-component. Teraz `requirements-dev.txt` ma go, ale `pytest.ini` wyłącza.**

---

## Fix #11 — Włącz pytest-homeassistant-custom-component

### SZUKAJ w tests/pytest.ini
    -p no:pytest_homeassistant_custom_component

### USUŃ tę linię

**Po tej zmianie większość testów PADNIE** — bo oczekują stubów, a dostają prawdziwe HA.
To jest pożądane — ujawnia gdzie testy były fasadą.

---

## Fix #12 — Przepisz conftest.py

Obecny conftest (912 linii) to głównie HA module stubs. Po Fix #11 (prawdziwe HA):
te stuby są zbędne albo szkodliwe (nadpisują rzeczywiste klasy).

### Cel nowego conftest.py:
```python
"""Test configuration for ThesslaGreen Modbus integration."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thessla_green_modbus.const import DOMAIN


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 10,
            "name": "Test Device",
            "connection_type": "tcp",
            "connection_mode": "tcp",
        },
        options={
            "scan_interval": 30,
            "timeout": 10,
            "retry": 3,
            "force_full_register_list": False,
        },
    )


def _fake_modbus_response(*, registers=None, bits=None):
    """Build a minimal pymodbus-like response object for tests."""
    from unittest.mock import MagicMock
    resp = MagicMock()
    resp.isError.return_value = False
    if registers is not None:
        resp.registers = registers
    if bits is not None:
        resp.bits = bits
    return resp
```

**Usuń:** wszystkie `types.ModuleType("homeassistant.*")` bloki, klasy ConfigEntry/ConfigFlow/DataUpdateCoordinator/HomeAssistant.

---

## Fix #13 — test_coordinator.py: usuń module-level HA stubs

**Problem:** Plik buduje 17 HA modułów od zera na poziomie modułu (przed importami!):
```python
ha = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
# ... 15 więcej
sys.modules["homeassistant"] = ha
```

Oznacza to że `ThesslaGreenModbusCoordinator` jest importowany z FAKE homeassistant.
`self.hass` to SimpleNamespace, `super().__init__()` to stub bez HA behavior.

### Co zrobić:
1. Usuń cały blok module-level stub (pierwsze ~130 linii)
2. Użyj `from homeassistant.core import HomeAssistant` bezpośrednio
3. Użyj `pytest.fixture` z prawdziwym `hass` z PHCC
4. Konstruuj coordinator przez `ThesslaGreenModbusCoordinator(hass, config, entry=mock_entry)`

Testy które sprawdzają logikę Modbus (timeout, retry, cancellation) **mogą zostać** — tylko usunąć stub infrastructure.

---

## Fix #14 — test_services.py: przepisz na HA fixtures

**Problem:** 18 HA module stubs + voluptuous stub. Testy sprawdzają czy service handler wywołuje `coordinator.async_write_register` z właściwymi argumentami — logika biznesowa testowana przez głęboki stub.

### Priorytet testów do zachowania (wysokiej wartości):
- `test_async_set_ventilation_speed` — testuje konkretną wartość rejestru
- `test_async_set_bypass` — testuje logikę trybu
- `test_get_entity_ids_from_call` — testuje parsowanie entity_ids

### Strategia refactoru:
```python
@pytest.fixture
async def services_hass(hass: HomeAssistant, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    coordinator = MagicMock(spec=ThesslaGreenModbusCoordinator)
    coordinator.async_write_register = AsyncMock(return_value=True)
    mock_config_entry.runtime_data = coordinator
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    return hass, coordinator
```

---

## Fix #15 — test_config_flow.py: 56 stubs to too much

**Problem:** config_flow.py ma 56 `sys.modules` manipulations. Test_config_flow powinien testować rzeczywisty przepływ konfiguracji przez HA.

### Przepisz kluczowe testy:
```python
async def test_config_flow_tcp_success(hass: HomeAssistant):
    """Config flow should create entry on successful TCP connection."""
    with patch("custom_components.thessla_green_modbus.config_flow._load_scanner_module") as mock_scanner:
        mock_scanner.return_value = AsyncMock(...)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
```

---

## Fix #16 — Specyficzne dummy/błędne testy do naprawy

### test_coordinator_coverage.py — coverage-driven tests (bad practice)
**Problem:** Plik istnieje "żeby osiągnąć coverage", nie żeby testować zachowanie.
Testuje linie, nie invarianty.

Przykład złego testu:
```python
def test_get_rtu_framer_returns_something():
    result = get_rtu_framer()
    assert result is not None  # ← co to sprawdza??
```

**Akcja:** Przejrzyj każdy test — jeśli assertion sprawdza tylko "czy nie None" bez kontekstu biznesowego → usuń lub przepisz z konkretnym oczekiwaniem.

### test_example_configuration.py — czy istnieje?
```bash
cat tests/test_example_configuration.py | head -30
```
Jeśli testuje tylko "czy można załadować JSON przykładu" → niskiej wartości.

### test_strings_json_generation.py i test_strings_translations.py
Testy generowania plików strings.json — **wartościowe**, zostaw.

### test_manifest_files.py
Testy poprawności manifest.json — **wartościowe**, zostaw.

### test_register_json_schema.py, test_register_uniqueness.py
Testy spójności danych JSON — **wysokiej wartości**, zostaw.

---

## Fix #17 — Usuń CoordinatorMock z conftest i test_optimized_integration.py

**Problem:** `CoordinatorMock` w conftest to ręcznie napisany mock koordynatora.
`test_optimized_integration.py` używa go zamiast prawdziwego coordinatora.

```bash
grep -n "CoordinatorMock" tests/conftest.py tests/test_optimized_integration.py | head -10
```

Jeśli `CoordinatorMock` reimplementuje zachowanie które `ThesslaGreenModbusCoordinator` już ma → zastąp przez `MagicMock(spec=ThesslaGreenModbusCoordinator)` lub prawdziwy coordinator z mock transport.

---

## Fix #18 — test_migration.py: zaktualizuj do nowej logiki

Po Fix #8 (v2/v3 → return False):

### SZUKAJ test który oczekuje v2 migration success
```python
async def test_migrate_entry_v2_adds_connection_type():
    config_entry.version = 2
    result = await async_migrate_entry(hass, config_entry)
    assert result is True  # ← to teraz False!
```

### ZASTĄP
```python
async def test_migrate_entry_v2_returns_false():
    """v2 entries are no longer supported since 2.8.0."""
    config_entry.version = 2
    result = await async_migrate_entry(hass, config_entry)
    assert result is False
```

Analogicznie dla v3. Test dla v1 już oczekuje False (z 2.5.0) — zostaw.

---

## Weryfikacja

```bash
# Baseline po legacy removal:
ruff check custom_components/ tests/ tools/
mypy custom_components/thessla_green_modbus/

# Testy — najpierw bez Fix #11 (bez prawdziwego HA):
pytest tests/ -x -q --ignore=tests/test_legacy_entity_id_aliases.py \
    --ignore=tests/test_legacy_entity_migration.py \
    --ignore=tests/test_services_legacy_ids.py

# Po Fix #11 (z prawdziwym HA — wymaga Python 3.13 + HA installed):
THESSLA_GREEN_USE_HA=1 pytest tests/ -x -q
```

---

## Bump + CHANGELOG

manifest.json + pyproject.toml: `version = "2.8.0"`

```markdown
## 2.8.0 — Legacy removal + test infrastructure overhaul (BREAKING)

### ⚠️ Breaking
- Config entry v2/v3 (pre-2023) no longer migrate — remove and re-add.
- Legacy service call entity IDs (`rekuperator_*`) no longer mapped —
  update automations to use current entity names.

### Removed
- Entity registry migrations (`async_migrate_entity_ids`, `async_migrate_unique_ids`)
  no longer run on startup — idempotent since 2022, dead after 2+ years.
- `_entity_registry_migrations.py`, `_legacy.py` (now dead code).
- `mappings/legacy.py` LEGACY_ENTITY_ID_OBJECT_ALIASES (70 entries) and
  `map_legacy_entity_id`.
- `scanner_io.py` shim (no importers). `tools/py_compile_all.py`.
- `"unit"` key from new config entries. v2/v3 migration paths.

### Tests
- Removed: `test_legacy_entity_id_aliases.py`, `test_legacy_entity_migration.py`,
  `test_services_legacy_ids.py`.
- Fixed: `test_migration.py` — v2/v3 now expect `False`.
- Infrastructure: `pytest-homeassistant-custom-component` plugin re-enabled,
  conftest.py rebuilt on real HA fixtures.
```

---

## Priorytet wykonania

```
Sprint 1 (niskie ryzyko, Fix #1-10): legacy removal
Sprint 2 (średnie ryzyko, Fix #11-12): test infrastructure
Sprint 3 (wysokie ryzyko, Fix #13-17): test rewrite per file
```

Sprint 2-3 można rozbić na osobne PR-y per plik testów.
