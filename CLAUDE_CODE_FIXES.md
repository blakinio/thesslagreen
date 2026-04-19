# thessla_green_modbus — instrukcja napraw dla Claude Code (v11)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main` (HEAD: `aea7cb9`)
**Wersja docelowa:** `2.4.2 → 2.5.0`
**Data audytu:** 2026-04-19

---

## Stan wyjściowy 2.4.2

- 🔴 **Ruff:** 2 errory — `F401` w `__init__.py:46`, `I001` w `coordinator.py:3`
- 🔴 **Mypy:** 10 errorów w 2 plikach
- 🔴 **RUNTIME:** `ImportError` przy starcie HA — `_coordinator_update.py:15` importuje `utcnow` z `utils`, której tam nie ma
- 🟡 Brak `.python-version` / `.tool-versions` dla pyenv/asdf
- 🟡 `pre-commit-config.yaml` bez jawnego `python3.13`, używa starego `black`+`isort` zamiast `ruff-format`
- 🟡 ~540 linii legacy: migracje v1, port 8899, polskie entity_ids, fan entity legacy, scanner shimsy

---

## Podział: 3 PR-y

- **PR 1 → patch 2.4.3:** Fixy #1-#4 (KRYTYCZNE — runtime bug, ruff, mypy)
- **PR 2 → patch 2.4.4:** Fixy #5-#8 (środowisko Python 3.13)
- **PR 3 → major 2.5.0:** Fixy #9-#17 (usunięcie legacy, breaking)

---

# CZĘŚĆ 1 — Krytyczne naprawy (2.4.3)

## Fix #1 — `utcnow` brakuje w `utils.py` (RUNTIME BUG)

**Problem:** `_coordinator_update.py:15` robi `from .utils import utcnow as _utcnow`, ale `utils.py` nie ma tej funkcji. Integracja nie uruchomi się w HA.

### Krok 1a — dodaj `utcnow` do `utils.py`

**Plik:** `custom_components/thessla_green_modbus/utils.py`

#### SZUKAJ
```python
from datetime import time
```

#### ZASTĄP
```python
from datetime import UTC, datetime, time
```

#### SZUKAJ
```python
def _to_snake_case(name: str) -> str:
```

#### ZASTĄP (wstaw przed)
```python
def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


def _to_snake_case(name: str) -> str:
```

### Krok 1b — uprość `_utcnow` w `coordinator.py`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

#### SZUKAJ
```python
def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return dt_util.utcnow()
```

#### ZASTĄP
```python
def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    from .utils import utcnow as _utils_utcnow
    return _utils_utcnow()
```

Uwaga: import wewnątrz funkcji unika circular import (coordinator.py jest importowany przez wiele miejsc). Alternatywnie dodaj `from .utils import utcnow as _utcnow` do bloku lokalnych importów na górze pliku i usuń funkcję — ale najpierw sprawdź czy circular import nie występuje:
```bash
python -c "from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator"
```

---

## Fix #2 — Typing w `_entity_registry_migrations.py` (9 mypy errorów)

**Plik:** `custom_components/thessla_green_modbus/_entity_registry_migrations.py`

#### SZUKAJ
```python
    candidates: dict[str, object] = {}
    for entity in all_platform_entries:
        candidates[entity.entity_id] = entity
    for entity in config_entry_list:
        candidates[entity.entity_id] = entity
```

#### ZASTĄP
```python
    candidates: dict[str, Any] = {}
    for entity in all_platform_entries:
        candidates[getattr(entity, "entity_id", "")] = entity
    for entity in config_entry_list:
        candidates[getattr(entity, "entity_id", "")] = entity
```

Sprawdź czy `Any` jest już importowany:
```bash
grep "from typing import" custom_components/thessla_green_modbus/_entity_registry_migrations.py | head -3
```

Jeśli nie — dodaj do istniejącego `from typing import ...` bloku.

Analogicznie dla pozostałych linii z mypy errorami (109, 116, 119, 124, 134, 139, 144) — zamień bezpośrednie dostępy do atrybutów `entity.entity_id`/`entity.unique_id` na `getattr(entity, "entity_id", "")` / `getattr(entity, "unique_id", "")`.

Sprawdź je wszystkie:
```bash
grep -n "entity\.entity_id\|entity\.unique_id" custom_components/thessla_green_modbus/_entity_registry_migrations.py
```

---

## Fix #3 — Ruff I001: import order w `coordinator.py`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

Najszybszy fix:
```bash
ruff check --fix custom_components/thessla_green_modbus/coordinator.py
```

Ręcznie — zamień kolejność bloków `_coordinator_*` (muszą być alfabetycznie):

#### SZUKAJ (linie 26-36)
```python
from ._coordinator_schedule import _CoordinatorScheduleMixin
from ._coordinator_register_processing import (
    create_consecutive_groups as _create_consecutive_groups_impl,
)
from ._coordinator_register_processing import (
    find_register_name as _find_register_name_impl,
)
from ._coordinator_register_processing import (
    process_register_value as _process_register_value_impl,
)
from ._coordinator_update import async_update_data as _async_update_data_impl
```

#### ZASTĄP
```python
from ._coordinator_register_processing import (
    create_consecutive_groups as _create_consecutive_groups_impl,
    find_register_name as _find_register_name_impl,
    process_register_value as _process_register_value_impl,
)
from ._coordinator_schedule import _CoordinatorScheduleMixin
from ._coordinator_update import async_update_data as _async_update_data_impl
```

---

## Fix #4 — Ruff F401: nieużywany `CONF_SLAVE_ID` w `__init__.py`

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

```bash
ruff check --fix --select F401 custom_components/thessla_green_modbus/__init__.py
```

Lub ręcznie:

#### SZUKAJ
```python
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_LOG_LEVEL,
```

#### ZASTĄP
```python
    CONF_SCAN_INTERVAL,
    DEFAULT_LOG_LEVEL,
```

### Weryfikacja Grupy A

```bash
ruff check custom_components/ tests/ tools/   # Expected: All checks passed!
mypy custom_components/thessla_green_modbus/  # Expected: Success: no issues found
```

### Bump dla PR 1

`manifest.json`: `"version": "2.4.3"` | `pyproject.toml`: `version = "2.4.3"`

```markdown
## 2.4.3 — Critical fix: ImportError at integration load

### Fixed
- `_coordinator_update.py` imported `utcnow` from `utils` but the function
  did not exist — integration failed to load in HA with `ImportError`. Added
  `utcnow()` helper to `utils.py`.
- Ruff I001 in `coordinator.py` (import order) and F401 in `__init__.py`
  (unused `CONF_SLAVE_ID`).
- 9 mypy errors in `_entity_registry_migrations.py` (`dict[str, object]`
  replaced with `dict[str, Any]` + `getattr` access).
```

---

# CZĘŚĆ 2 — Środowisko Python 3.13 (2.4.4)

## Fix #5 — `.python-version` dla pyenv

**Plik:** `.python-version` (NOWY, root)

```
3.13
```

## Fix #6 — `.tool-versions` dla asdf

**Plik:** `.tool-versions` (NOWY, root)

```
python 3.13.0
```

## Fix #7 — Przebuduj `.pre-commit-config.yaml`

**Plik:** `.pre-commit-config.yaml`

Obecna konfiguracja ma trzy problemy:
1. Brak `default_language_version: python: python3.13`
2. Używa `black` + `isort` — projekt używa `ruff` dla formatu i sortowania
3. `mypy` sprawdza tylko `registers/` zamiast całego pakietu

#### ZASTĄP cały plik
```yaml
default_language_version:
  python: python3.13

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        pass_filenames: false
        args:
          - "--config-file=pyproject.toml"
          - "custom_components/thessla_green_modbus"
        additional_dependencies:
          - types-PyYAML>=6.0.12
          - pymodbus>=3.6.0
          - voluptuous>=0.13.1
          - pydantic>=2,<3

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
      - id: check-json
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

## Fix #8 — `__init__.py`: explicit Python version check

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

#### SZUKAJ
```python
"""ThesslaGreen Modbus integration for Home Assistant."""

from __future__ import annotations
```

#### ZASTĄP
```python
"""ThesslaGreen Modbus integration for Home Assistant."""

from __future__ import annotations

import sys as _sys

if _sys.version_info < (3, 13):
    raise RuntimeError(
        f"ThesslaGreen Modbus requires Python 3.13+; "
        f"running on {_sys.version_info.major}.{_sys.version_info.minor}. "
        "Update Home Assistant to 2026.1.0+ which ships Python 3.13."
    )
```

## Fix #9 — README: sekcja Development

**Plik:** `README.md` — dodaj sekcję (lub `CONTRIBUTING.md` jeśli istnieje):

```markdown
## Development

**Python 3.13 is required** (matches Home Assistant 2026.1+).

```bash
pyenv install 3.13 && pyenv local 3.13   # lub: asdf install python 3.13.0
pip install -r requirements-dev.txt
pre-commit install
ruff check custom_components/ tests/ tools/
mypy custom_components/thessla_green_modbus/
pytest tests/ -x -q
```

> **Note for Codex / AI agents:** The integration uses `enum.StrEnum`
> (Python 3.11+). Running `pytest` in a container with Python < 3.13 will
> fail at import with `ImportError: cannot import name 'StrEnum' from 'enum'`.
> This is expected — the test environment must use Python 3.13.
```

### Bump dla PR 2

`manifest.json`: `"version": "2.4.4"` | `pyproject.toml`: `version = "2.4.4"`

```markdown
## 2.4.4 — Python 3.13 environment enforcement

### Added
- `.python-version` (pyenv) and `.tool-versions` (asdf) declare Python 3.13.
- Explicit `sys.version_info` check in `__init__.py` — clear error on older Python.
- `.pre-commit-config.yaml` rebuilt: `default_language_version: python3.13`,
  replaced `black`+`isort` with `ruff-format`, expanded mypy scope to full package.
- README development setup section.
```

---

# CZĘŚĆ 3 — Usunięcie legacy (2.5.0, BREAKING)

## Fix #10 — Usuń migrację `config_entry.version == 1` (pre-2021)

**Plik:** `custom_components/thessla_green_modbus/_entry_migrations.py`

#### SZUKAJ
```python
    if config_entry.version == 1:
        if "unit" in new_data and CONF_SLAVE_ID not in new_data:
            new_data[CONF_SLAVE_ID] = new_data["unit"]
            _LOGGER.info("Migrated 'unit' to '%s'", CONF_SLAVE_ID)

        if CONF_PORT not in new_data:
            new_data[CONF_PORT] = LEGACY_DEFAULT_PORT
            _LOGGER.info("Added '%s' with legacy default %s", CONF_PORT, LEGACY_DEFAULT_PORT)

        if CONF_SCAN_INTERVAL not in new_options:
            new_options[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        if CONF_TIMEOUT not in new_options:
            new_options[CONF_TIMEOUT] = DEFAULT_TIMEOUT
        if CONF_RETRY not in new_options:
            new_options[CONF_RETRY] = DEFAULT_RETRY
        if CONF_FORCE_FULL_REGISTER_LIST not in new_options:
            new_options[CONF_FORCE_FULL_REGISTER_LIST] = False

        config_entry.version = 2
```

#### ZASTĄP
```python
    if config_entry.version == 1:
        _LOGGER.error(
            "ThesslaGreen Modbus: config entry version 1 (pre-2021) is no longer "
            "supported. Please remove and re-add the integration."
        )
        return False
```

## Fix #11 — Usuń `LEGACY_DEFAULT_PORT = 8899`

**Plik:** `custom_components/thessla_green_modbus/_entry_migrations.py`

#### SZUKAJ
```python
LEGACY_DEFAULT_PORT = 8899
```

#### USUŃ (całą linię)

Zamień wszystkie użycia `LEGACY_DEFAULT_PORT` na `DEFAULT_PORT`:
```bash
grep -n "LEGACY_DEFAULT_PORT" custom_components/thessla_green_modbus/_entry_migrations.py
```

Sprawdź testy:
```bash
grep -rn "LEGACY_DEFAULT_PORT\|8899" tests/ --include="*.py"
```
Zaktualizuj — użyj `port=8899` explicit tam gdzie testy migracji wymagają tej konkretnej wartości.

## Fix #12 — Usuń polskie entity_id aliasy z `mappings/legacy.py`

**Plik:** `custom_components/thessla_green_modbus/mappings/legacy.py`

#### SZUKAJ (w `LEGACY_ENTITY_ID_OBJECT_ALIASES`)
```python
    # Polish-language entity IDs (installations with HA language set to pl before 2026)
    "rekuperator_moc_odzysku_ciepla": ("sensor", "rekuperator_heat_recovery_power"),
    "rekuperator_sprawnosc_rekuperatora": ("sensor", "rekuperator_heat_recovery_efficiency"),
    "rekuperator_pobor_mocy_elektrycznej": ("sensor", "rekuperator_electrical_power"),
```

#### USUŃ te 4 linie (wpisy + komentarz)

Sprawdź czy są kolejne z nieanglieskim słowem jako klucz:
```bash
grep -n "rekuperator_[a-z]*[ą-ż]" custom_components/thessla_green_modbus/mappings/legacy.py
```

## Fix #13 — Usuń `LEGACY_FAN_ENTITY_IDS` i fan entity cleanup

### Krok 13a — `_legacy.py`

**Plik:** `custom_components/thessla_green_modbus/_legacy.py`

#### SZUKAJ
```python
# Legacy entity IDs that were replaced by the fan entity
LEGACY_FAN_ENTITY_IDS = [
    "number.rekuperator_predkosc",
    "number.rekuperator_speed",
]
```

#### USUŃ (4 linie)

### Krok 13b — `_entity_registry_migrations.py`

Usuń w całości funkcję `async_cleanup_legacy_fan_entity`:
```bash
grep -n "def async_cleanup_legacy_fan_entity" custom_components/thessla_green_modbus/_entity_registry_migrations.py
```

Usuń od `async def async_cleanup_legacy_fan_entity` do następnej funkcji na tym samym poziomie wcięcia.

### Krok 13c — `__init__.py`

#### SZUKAJ
```python
    await _async_cleanup_legacy_fan_entity(hass, coordinator)
```
#### USUŃ

#### SZUKAJ (w bloku importów)
```python
    async_cleanup_legacy_fan_entity as _async_cleanup_legacy_fan_entity,
```
#### USUŃ

### Krok 13d — `_migrations.py`

```bash
grep -n "async_cleanup_legacy_fan_entity" custom_components/thessla_green_modbus/_migrations.py
```
Usuń linię z listy importów i z `__all__` jeśli jest tam wymienione.

### Krok 13e — `mappings/legacy.py`: usuń `predkosc`/`speed` aliasy

#### SZUKAJ
```python
LEGACY_ENTITY_ID_ALIASES: dict[str, tuple[str, str]] = {
    # "number.rekuperator_predkosc" / "number.rekuperator_speed" → fan entity
    "predkosc": ("fan", "fan"),
    "speed": ("fan", "fan"),
}
```

#### ZASTĄP (lub usuń cały dict jeśli pusty po cleanup)
```python
LEGACY_ENTITY_ID_ALIASES: dict[str, tuple[str, str]] = {}
```

Jeśli dict pusty — szukaj wszystkich użyć i usuń:
```bash
grep -rn "LEGACY_ENTITY_ID_ALIASES" custom_components/ --include="*.py"
```

### Weryfikacja fix #13
```bash
grep -rn "LEGACY_FAN_ENTITY_IDS\|async_cleanup_legacy_fan_entity" custom_components/ --include="*.py"
# Expected: 0 wyników
```

## Fix #14 — Udokumentuj `BIT_ENTITY_KEYS` jako "not legacy"

**Plik:** `custom_components/thessla_green_modbus/_legacy.py`

#### SZUKAJ
```python
# Mapping from (register_key, bit_value) → bit-specific entity key.
# Used during migration to assign unique entity_ids to individual bits of
# bitmask registers.  Without this, all 4 bits of e_196_e_199 would all
# target the same entity_id (collision) and only one could be migrated.
BIT_ENTITY_KEYS: dict[tuple[str, int], str] = {
```

#### ZASTĄP
```python
# Mapping from (register_key, bit_value) → bit-specific entity key.
#
# NOT LEGACY — this is an active functional requirement. The e_196_e_199
# register is a 4-bit bitmask; each bit maps to a separate binary_sensor
# entity (E196..E199). Without this map all 4 bits would collide on the
# same entity_id. Do not remove.
BIT_ENTITY_KEYS: dict[tuple[str, int], str] = {
```

## Fix #15 — `LEGACY_KEY_RENAMES`: dodaj deprecation schedule

**Plik:** `custom_components/thessla_green_modbus/_legacy.py`

#### SZUKAJ
```python
# Map old register keys (as they appeared in unique_ids) to current keys.
# Needed for entities where the dict_key itself was renamed across versions,
# not just the entity_id naming mechanism (translation → key-based).
LEGACY_KEY_RENAMES: dict[str, str] = {
```

#### ZASTĄP
```python
# Map old register keys to current keys for unique_id migration.
#
# DEPRECATION SCHEDULE: entries older than 2 years are candidates for
# removal in 2.7.0+ (planned end-2026). When adding new entries, annotate
# the version in which the rename happened, e.g.:
#   "old_key": "new_key",  # renamed in 2.3.0
LEGACY_KEY_RENAMES: dict[str, str] = {
```

## Fix #16 — Usuń shim `scanner_core.py`

### Krok 16a — znajdź użycia w testach

```bash
grep -rn "scanner_core" tests/ --include="*.py" | head -20
```

### Krok 16b — zamień ścieżki importów w testach

Dla każdego wystąpienia `custom_components.thessla_green_modbus.scanner_core`:

```python
# Było:
"custom_components.thessla_green_modbus.scanner_core.ThesslaGreenDeviceScanner.create"
# Ma być:
"custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
```

### Krok 16c — usuń plik

```bash
rm custom_components/thessla_green_modbus/scanner_core.py
```

## Fix #17 — Uprość shim `scanner_io.py`

**Plik:** `custom_components/thessla_green_modbus/scanner_io.py`

Sprawdź które funkcje są faktycznie używane przez produkcję:
```bash
grep -rn "from \.\.scanner_io\|from \. import scanner_io\|scanner_io\." custom_components/thessla_green_modbus/ --include="*.py"
```

Sprawdź że `is_request_cancelled_error` i `ensure_pymodbus_client_module` są już w `scanner/io.py`:
```bash
grep -n "def is_request_cancelled_error\|def ensure_pymodbus_client_module" custom_components/thessla_green_modbus/scanner/io.py
```

Jeśli są — **zastąp całą zawartość `scanner_io.py`** cienkim shimem:

#### ZASTĄP całą zawartość
```python
"""Backward compatibility shim — moved to scanner.io."""

from __future__ import annotations

from .scanner.io import (
    ensure_pymodbus_client_module,
    is_request_cancelled_error,
)

__all__ = ["ensure_pymodbus_client_module", "is_request_cancelled_error"]
```

Zaktualizuj importy wewnątrz `scanner/*.py` (które robią `from .. import scanner_io as _scanner_io`) żeby importowały z `scanner/io.py` bezpośrednio.

---

## Weryfikacja końcowa

```bash
ruff check custom_components/ tests/ tools/         # 0 findings
mypy custom_components/thessla_green_modbus/        # 0 errors
python tools/compare_registers_with_reference.py    # pass
```

---

## Bump i CHANGELOG (2.5.0)

`manifest.json`: `"version": "2.5.0"` | `pyproject.toml`: `version = "2.5.0"`

```markdown
## 2.5.0 — Legacy cleanup (BREAKING)

### ⚠️ Breaking changes
- Config entry version 1 (pre-2021) no longer migrates automatically — remove
  and re-add the integration.
- Polish-language entity IDs (`rekuperator_moc_odzysku_ciepla` etc.) no longer
  have migration aliases — update automations to use current English entity names.
- Legacy fan entity IDs (`number.rekuperator_predkosc`, `number.rekuperator_speed`)
  are not cleaned up automatically — remove them manually from entity registry if
  present.

### Removed
- `config_entry.version == 1` migration path.
- `LEGACY_DEFAULT_PORT = 8899` constant.
- Polish-language entity_id aliases in `mappings/legacy.py`.
- `LEGACY_FAN_ENTITY_IDS` list and `async_cleanup_legacy_fan_entity` function.
- `predkosc`/`speed` entries from `LEGACY_ENTITY_ID_ALIASES`.
- `scanner_core.py` shim — use `scanner.core` directly.

### Changed
- `scanner_io.py` reduced to thin re-export shim of `scanner/io.py`.
- `BIT_ENTITY_KEYS` documented as active functional requirement (e_196_e_199
  bitmask), not legacy.
- `LEGACY_KEY_RENAMES` annotated with deprecation schedule (2.7.0+).
```

---

## Metryki docelowe

```
                            2.4.2 (obecne)    2.4.3    2.4.4    2.5.0
Ruff findings:              2                 0        0        0
Mypy errors:                10                0        0        0
Runtime ImportError:        Tak               Nie      Nie      Nie
Python 3.13 enforced:       1 layer           1        5        6
Legacy migration v1:        Present           →        →        Removed
Polish entity aliases:      3                 →        →        0
scanner_core.py shim:       16 linii          →        →        Removed
Linie legacy kodu:          ~540              →        →        ~200
```
