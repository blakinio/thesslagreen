# thessla_green_modbus — instrukcja napraw dla Claude Code (v12)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main` (HEAD: `dba1a47` — merge PR #1331)
**Wersja docelowa:** `2.5.0 → 2.5.1`
**Data audytu:** 2026-04-19

---

## Stan po 2.5.0

✅ Ruff: 0 | Mypy: 0 (58 plików) | Baseline przywrócony po regresji z 2.4.2  
✅ `utcnow()` w `utils.py` — runtime ImportError naprawiony  
✅ `_compat.py` — czyste re-exports, brak fallbacków  
✅ `CoordinatorConfig` dataclass — `__init__` przyjmuje `config: CoordinatorConfig` (Fix #9 z v8 w końcu wdrożony)  
✅ `.python-version` (3.13), `.tool-versions` (python 3.13.0)  
✅ `pre-commit-config.yaml` — `python3.13`, `ruff-format` zamiast `black`+`isort`  
✅ `sys.version_info` check w `__init__.py`  
✅ Legacy usunięte: polskie entity_ids, `LEGACY_FAN_ENTITY_IDS`, `LEGACY_DEFAULT_PORT`, `scanner_core.py`  
✅ `scanner_io.py` — 10-liniowy shim re-exportujący z `scanner/io.py`

**Pozostałe smelle znalezione w tej turze:**

| # | Plik | Smell |
|---|---|---|
| 1 | `config_flow.py:565-592` | 5 metod `ConfigFlow` z `getattr(super(), ...)` fallback — test-compat |
| 2 | `_entity_registry_migrations.py:38` | `except (ImportError, ModuleNotFoundError, AttributeError): return` dla HA helpers — dead path |
| 3 | `config_flow.py:112-122` | `_load_scanner_module` z `getattr(hass, "async_add_executor_job", None)` — SimpleNamespace fallback |
| 4 | `_legacy.py` | `BIT_ENTITY_KEYS` komentarz nie-legacy nie dodany |
| 5 | `config_flow.py` | 43× `# pragma: no cover` — wysoka gęstość |

**Priorytet: niski-średni.** Funkcjonalność działa, to cleanup jakościowy. Minor bump.

---

## Fix #1 — `ConfigFlow` defensive method wrappers

**Plik:** `custom_components/thessla_green_modbus/config_flow.py`

**Dowód (linie 565-592):**
```python
async def async_set_unique_id(self, *args, **kwargs):  # pragma: no cover - defensive
    base = getattr(super(), "async_set_unique_id", None)
    if callable(base):
        result = base(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    return None

def _abort_if_unique_id_configured(self, **kwargs):  # pragma: no cover - defensive
    base = getattr(super(), "_abort_if_unique_id_configured", None)
    if callable(base):
        return base(**kwargs)
    return None

def async_show_form(self, **kwargs):  # pragma: no cover - defensive
    base = getattr(super(), "async_show_form", None)
    if callable(base):
        return base(**kwargs)
    return {"type": "form", **kwargs}

def async_create_entry(self, **kwargs):  # pragma: no cover - defensive
    base = getattr(super(), "async_create_entry", None)
    if callable(base):
        return base(**kwargs)
    return {"type": "create_entry", **kwargs}

def async_abort(self, **kwargs):  # pragma: no cover - defensive
    base = getattr(super(), "async_abort", None)
    if callable(base):
        return base(**kwargs)
    return {"type": "abort", **kwargs}
```

**Problem:** `ConfigFlow` dziedziczy z `_ConfigFlowBase = config_entries.ConfigFlow`. Wszystkie te metody (`async_set_unique_id`, `_abort_if_unique_id_configured`, `async_show_form`, `async_create_entry`, `async_abort`) istnieją w `homeassistant.config_entries.ConfigFlow` od co najmniej HA 2022. Manifest wymaga HA 2026.1.0. `getattr(super(), "method", None)` dla metod które **zawsze istnieją** to wzorzec z czasów gdy testy używały stubów bez pełnego HA.

### Krok 1 — zastąp defensive wrappers prostymi delegatami

#### SZUKAJ (linie ~565-593)
```python
    async def async_set_unique_id(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - defensive
        base = getattr(super(), "async_set_unique_id", None)
        if callable(base):
            result = base(*args, **kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result
        return None

    def _abort_if_unique_id_configured(self, **kwargs: Any) -> Any:  # pragma: no cover - defensive
        base = getattr(super(), "_abort_if_unique_id_configured", None)
        if callable(base):
            return base(**kwargs)
        return None

    def async_show_form(self, **kwargs: Any) -> Any:  # pragma: no cover - defensive
        base = getattr(super(), "async_show_form", None)
        if callable(base):
            return base(**kwargs)
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> Any:  # pragma: no cover - defensive
        base = getattr(super(), "async_create_entry", None)
        if callable(base):
            return base(**kwargs)
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs: Any) -> Any:  # pragma: no cover - defensive
        base = getattr(super(), "async_abort", None)
        if callable(base):
            return base(**kwargs)
        return {"type": "abort", **kwargs}
```

#### USUŃ wszystkie 5 metod w całości

`ConfigFlow` odziedziczy te metody bezpośrednio z `homeassistant.config_entries.ConfigFlow`. Żadna nadpisana implementacja nie jest potrzebna.

### Krok 1b — sprawdź `VERSION = 4`

```python
VERSION = 4  # pragma: no cover - defensive
```

`# pragma: no cover - defensive` na stałej klasowej to nonsens — to nie jest kod który się "wykonuje" lub nie. Usuń komentarz:

#### SZUKAJ
```python
    VERSION = 4  # pragma: no cover - defensive
```

#### ZASTĄP
```python
    VERSION = 4
```

### Weryfikacja
```bash
ruff check custom_components/thessla_green_modbus/config_flow.py
mypy custom_components/thessla_green_modbus/config_flow.py
pytest tests/test_config_flow.py -x -q
```

### Oczekiwany efekt
- −30 linii defensywnego kodu
- −5 `# pragma: no cover` z `config_flow.py` (43 → ~38)

---

## Fix #2 — `except (ImportError, ModuleNotFoundError)` dla HA helpers

**Plik:** `custom_components/thessla_green_modbus/_entity_registry_migrations.py`

**Dowód (linie 38-40):**
```python
    try:
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.util import slugify
    except (ImportError, ModuleNotFoundError, AttributeError):
        return
```

**Problem:** `homeassistant.helpers.entity_registry`, `device_registry`, i `homeassistant.util.slugify` są w HA od 2019. Manifest wymaga HA 2026.1.0. Ten `try/except` jest dead path — **jeśli import padnie, byłby to błąd w instalacji HA, nie edge case**. Cichy `return` maskuje taką awarię.

### Krok 2 — usuń try/except, importy na poziomie modułu

**Plik:** `custom_components/thessla_green_modbus/_entity_registry_migrations.py`

Sprawdź nagłówek pliku — co jest już importowane:
```bash
head -25 custom_components/thessla_green_modbus/_entity_registry_migrations.py
```

#### SZUKAJ (w ciele funkcji `async_migrate_entity_ids` lub podobnej)
```python
    try:
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        from homeassistant.util import slugify
    except (ImportError, ModuleNotFoundError, AttributeError):
        return
```

#### ZASTĄP
```python
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import slugify
```

Alternatywnie (lepiej) — przenieś te importy na top-level pliku jeśli używane w wielu funkcjach:

```python
# Na górze pliku, po istniejących importach:
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
```

Usuń wtedy te local importy całkowicie.

### Oczekiwany efekt
- −5 linii try/except
- Awaria importu HA będzie widoczna jako jawny błąd, nie ciche `return`

---

## Fix #3 — `_load_scanner_module` SimpleNamespace fallback

**Plik:** `custom_components/thessla_green_modbus/config_flow.py`

**Dowód (linie 112-122):**
```python
async def _load_scanner_module(hass: Any) -> Any:
    """Import scanner.core using the HA executor when available.

    Falls back to a direct synchronous import when *hass* is ``None`` or does
    not expose ``async_add_executor_job`` (e.g. SimpleNamespace test stubs).
    """
    module_name = "custom_components.thessla_green_modbus.scanner.core"
    _aej = getattr(hass, "async_add_executor_job", None)
    if _aej is not None:
        result = _aej(import_module, module_name)
        if inspect.isawaitable(result):
            return await result
    return import_module(module_name)
```

**Problem:** `hass.async_add_executor_job` istnieje w każdym prawdziwym HA `HomeAssistant` obiekcie. `getattr(hass, "async_add_executor_job", None)` jest fallbackiem dla SimpleNamespace (testy bez HA). Po v2.4.0 detox testy powinny używać prawdziwego `hass` fixture.

### Krok 3 — uprość

#### SZUKAJ
```python
async def _load_scanner_module(hass: Any) -> Any:
    """Import scanner.core using the HA executor when available.

    Falls back to a direct synchronous import when *hass* is ``None`` or does
    not expose ``async_add_executor_job`` (e.g. SimpleNamespace test stubs).
    """
    module_name = "custom_components.thessla_green_modbus.scanner.core"
    _aej = getattr(hass, "async_add_executor_job", None)
    if _aej is not None:
        result = _aej(import_module, module_name)
        if inspect.isawaitable(result):
            return await result
    return import_module(module_name)
```

#### ZASTĄP
```python
async def _load_scanner_module(hass: HomeAssistant) -> Any:
    """Import scanner.core via the HA executor to avoid blocking the event loop."""
    module_name = "custom_components.thessla_green_modbus.scanner.core"
    return await hass.async_add_executor_job(import_module, module_name)
```

### Krok 3b — sprawdź typ `hass` w signature callerów

```bash
grep -n "_load_scanner_module" custom_components/thessla_green_modbus/config_flow.py
```

Jeśli caller przekazuje `hass: Any` — zmień na `hass: HomeAssistant`. Sprawdź czy `HomeAssistant` jest importowany w pliku:
```bash
grep "from homeassistant.core import" custom_components/thessla_green_modbus/config_flow.py
```

### Krok 3c — czy `inspect` jest wciąż używany?

```bash
grep -n "\binspect\." custom_components/thessla_green_modbus/config_flow.py
```

Jeśli `inspect.isawaitable` był jedynym użyciem po tej zmianie — usuń `import inspect`.

### Oczekiwany efekt
- −6 linii
- Czystsza sygnatura (nie `Any` ale `HomeAssistant`)
- Mniej defensywnego kodu

---

## Fix #4 — `BIT_ENTITY_KEYS` — brak "not legacy" komentarza

**Plik:** `custom_components/thessla_green_modbus/_legacy.py`

**Dowód:**
```python
BIT_ENTITY_KEYS: dict[tuple[str, int], str] = {
    # e_196_e_199 is a bitmask register; each bit gets its own entity key.
    # Key format: _to_snake_case(bit_name) inserts underscore before digits,
    # so "e196" → "e_196", giving "e_196_e_199_e_196".
    (\"e_196_e_199\", 1): \"e_196_e_199_e_196\",
```

Komentarz z v11 o tym że to NOT LEGACY nie został dodany.

### Krok 4

**Plik:** `custom_components/thessla_green_modbus/_legacy.py`

#### SZUKAJ
```python
BIT_ENTITY_KEYS: dict[tuple[str, int], str] = {
    # e_196_e_199 is a bitmask register; each bit gets its own entity key.
    # Key format: _to_snake_case(bit_name) inserts underscore before digits,
    # so "e196" → "e_196", giving "e_196_e_199_e_196".
```

#### ZASTĄP
```python
# NOT LEGACY — active functional requirement. The e_196_e_199 register is a
# 4-bit bitmask; each bit maps to a separate binary_sensor entity (E196-E199).
# Without this map all 4 bits would collide on the same entity_id.
# Do not remove unless the underlying hardware/protocol changes.
BIT_ENTITY_KEYS: dict[tuple[str, int], str] = {
    # Key format: _to_snake_case(bit_name) inserts underscore before digits,
    # so "e196" → "e_196", giving "e_196_e_199_e_196".
```

---

## Fix #5 — Redukcja `# pragma: no cover` w `config_flow.py`

**Plik:** `custom_components/thessla_green_modbus/config_flow.py` (43 pragmas)

Po Fix #1 (usunięcie 5 defensive methods) zostanie ~38. Pozostałe to głównie linie w error-handling paths które nie są pokryte testami.

### Krok 5 — audit remaining pragmas

```bash
grep -n "# pragma: no cover" custom_components/thessla_green_modbus/config_flow.py
```

Dla każdego `# pragma: no cover - defensive` zadaj pytanie:
- Czy ta linia/blok jest w rzeczywistości nieosiągalny w produkcji?
- Czy nieosiągalność wynika z logiki kodu, czy z braku testu?

**Decyzja per kategoria:**

| Pattern | Akcja |
|---|---|
| `raise` po `except` który właśnie obsłużył inny wyjątek | Zostaw (faktycznie defensive) |
| `return {"type": "form", ...}` w usuniętych wrapperach | Usuwa się z Fix #1 |
| `VERSION = 4` | Usuwa się z Fix #1 |
| Error logging w `except` bloku który jest przetestowany | Rozważ usunięcie pragma i dodanie testu |

Priorytet: usuń pragmas które wylądowały "bo test nie istnieje" — dodaj test albo zaakceptuj jako defensive.

---

## Weryfikacja końcowa

```bash
ruff check custom_components/ tests/ tools/
# Expected: All checks passed!

mypy custom_components/thessla_green_modbus/
# Expected: Success: no issues found in 58 source files

pytest tests/ -x -q
# Na Python 3.13 z HA: wszystkie przechodzą
```

---

## Bump i CHANGELOG

`manifest.json`: `"version": "2.5.1"` | `pyproject.toml`: `version = "2.5.1"`

```markdown
## 2.5.1 — Config flow cleanup

### Removed
- 5 defensive `getattr(super(), ...)` method wrappers in `ConfigFlow`
  (`async_set_unique_id`, `_abort_if_unique_id_configured`, `async_show_form`,
  `async_create_entry`, `async_abort`). These methods exist in
  `homeassistant.config_entries.ConfigFlow` since HA 2022; the fallbacks
  were test-compat code for SimpleNamespace stubs.
- `try/except ImportError` guard around `homeassistant.helpers` imports in
  `_entity_registry_migrations.py`. HA helpers are always available given
  manifest requirement >=2026.1.0.

### Changed
- `_load_scanner_module` in `config_flow.py` simplified: removed
  `getattr(hass, "async_add_executor_job", None)` fallback, now uses
  `hass.async_add_executor_job` directly. Parameter type narrowed from
  `Any` to `HomeAssistant`.
- `BIT_ENTITY_KEYS` in `_legacy.py` documented as "NOT LEGACY — active
  functional requirement" to prevent accidental removal in future cleanups.
- `VERSION = 4` class attribute in `ConfigFlow` no longer has spurious
  `# pragma: no cover - defensive` annotation.
```

---

## Odłożone (nie w tym release)

**`config_flow.py` 38+ `# pragma: no cover`** — wymaga napisania dodatkowych testów dla error paths w `_validate_connection`. Osobna praca.

**`_entity_registry_migrations.py` — `list[object]` dla `config_entry_list`** — po Fix #2 (import na top-level) można dodać property type na `RegistryEntry` i usunąć `getattr` pattern na atrybutach. Niskopriorytowe.

**`modbus_helpers.py:36` — `inspect.signature`** — użyte do detekcji pymodbus API version. **Legit** — różne wersje pymodbus mają różną signature dla `read_holding_registers`. Nie ruszać.

**`scanner/io.py:624 linii`** — największy moduł po scaleniu logiiki z `scanner_io.py`. Kandydat do przyszłego podziału.
