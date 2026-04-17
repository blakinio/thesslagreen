# thessla_green_modbus — instrukcja napraw dla Claude Code (v8)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main` (HEAD: `a6535b9` — merge PR #1328)
**Wersja docelowa:** `2.4.0 → 2.4.1`
**Data audytu:** 2026-04-17

---

## Stan po wdrożeniu v7 (świetne wyniki)

**Baseline 2.4.0:**
- ✅ **Ruff:** 0 findings
- ✅ **Mypy strict:** 0 errors w **50 plikach** (−5 od v2.3.9)
- ✅ **Zero TODO/FIXME/HACK**
- ✅ **`_compat.py`:** 144 → 75 linii (martwe fallbacki usunięte)
- ✅ Wszystkie 17 fixów z v7 zmerdżowane (PR #1328)
- ✅ Fixes z v1-v6 wdrożone (ruff 0, mypy 0, scanner split, martwy kod usunięty, cross-validation z PDF dodana)

**Co się zmieniło:**
- Usunięte: `_scanner_*_mixin.py` (3 pliki), `register_addresses.py`, `entity_mappings.py`, `validate.yaml`
- `_update_failed_exception`, `_PermissiveCapabilities`, `_async_patch_coordinator_compat`, `_SafeDTUtil` — wszystkie usunięte
- Alias `__init__.er` + shim dla `tests/__init__.er` — usunięty
- Pyflakes step z CI — usunięty (ruff pokrywa)
- Nowy skrypt `tools/compare_registers_with_reference.py` + test cross-validation z PDF
- `scanner_core.py` jest re-export shimem dla `scanner.core`

---

## Cel v2.4.1 — dokończenie detoxu

V7 usunęło **większość** śladów "produkcja-pod-testy", ale audyt v2.4.0 znalazł **8 pozostałych miejsc** gdzie production code wciąż wie o testach:

- Skanowanie `sys.modules` dla `"pytest"` żeby zmienić zachowanie
- Wrappery z komentarzem "test patch compatibility"
- `inspect.signature` check'i na własnych metodach żeby uniknąć "mock context" błędów
- Dynamic imports przez `sys.modules` check żeby testy mogły patchować moduły
- Defensywne `try/except TypeError: _LOGGER.debug("Skipping in mock context")`
- Trywialne wrappery `_schema`/`_required` które nic nie robią po cleanup v7

**Plus 4 odłożone pozycje architekturalne** z poprzednich audytów (dataclass CoordinatorConfig, split scanner/core, split __init__.py, config_flow follow-up).

**To minor bump** (2.4.1) bo:
- Fixy są czysto removalsami — nie dodają funkcjonalności.
- Brak breaking change w publicznym API.
- Testy wymagają mniejszej pracy niż v7 (większość prace została zrobiona).

---

## Zakres i kolejność

**Grupa A — Ostatnie test-induced smelly (niskie/średnie ryzyko):**

1. Fix #1 — Usunięcie `_compat_asdict` w `scanner_device_info.py`
2. Fix #2 — Usunięcie `inspect.signature` filtering w `__init__.py:274`
3. Fix #3 — Usunięcie `sys.modules.get()` check przed dynamicznym importem coordinator
4. Fix #4 — Usunięcie `"Skipping in mock context"` try/except w `__init__.py:362`
5. Fix #5 — Usunięcie `_HAS_HA` + `"pytest" in sys.modules` w `const.py`
6. Fix #6 — Uproszczenie `_create_scanner` w `coordinator.py` (usunięcie dynamic self-import)
7. Fix #7 — Usunięcie `inspect.signature(write_cb)` check w `entity.py`
8. Fix #8 — Usunięcie trywialnych wrapperów `_schema`/`_required` w `config_flow.py`

**Grupa B — Architekturalne (odłożone; nie w tym release):**

- Fix #9 (tracked) — Dataclass `CoordinatorConfig` (24-param `__init__`)
- Fix #10 (tracked) — Split `scanner/core.py` (1596 linii)
- Fix #11 (tracked) — Split `__init__.py` (1067 linii)
- Fix #12 (tracked) — Dalsza redukcja `# pragma: no cover` w `config_flow.py` (46 wciąż obecnych)

Po każdym fixie:
```bash
ruff check custom_components/ tests/ tools/
mypy custom_components/thessla_green_modbus/
pytest tests/ -x -q
```

---

## Fix #1 — Usuń `_compat_asdict` w `scanner_device_info.py`

**Plik:** `custom_components/thessla_green_modbus/scanner_device_info.py`

**Dowód (linie 13-20):**
```python
def _compat_asdict(obj: Any) -> dict[str, Any]:
    """Use scanner_core.asdict when available (test patch compatibility)."""

    try:
        from . import scanner_core as _scanner_core

        return _scanner_core.asdict(obj)
    except (ImportError, AttributeError, TypeError):  # pragma: no cover - fallback
        return dataclasses.asdict(obj)
```

**Co to robi:** funkcja importuje `scanner_core` (który jest shimem dla `scanner.core`), pobiera `asdict` i wywołuje ją. `scanner_core.asdict = _dataclasses_asdict` — czyli to jest **dokładnie to samo** co `dataclasses.asdict` — tylko z jedną dodatkową warstwą indirekcji. Komentarz mówi wprost: *"test patch compatibility"*.

**Jedyny użyteczny cel:** gdyby testy patchowały `scanner_core.asdict` na custom funkcję.

**Weryfikacja — kto patchuje `scanner_core.asdict`?**
```bash
grep -rn "scanner_core\.asdict\|scanner_core.*asdict" tests/ --include="*.py"
```

Jeśli grep zwraca 0 wyników → funkcja jest martwa. Jeśli coś zwraca → naprawić testy żeby patchowały `dataclasses.asdict` (właściwy symbol).

### Krok 1a — znajdź callery `_compat_asdict`

```bash
grep -rn "_compat_asdict" custom_components/ tests/ --include="*.py"
```

### Krok 1b — zastąp wywołania przez `dataclasses.asdict`

W każdym miejscu gdzie `_compat_asdict(obj)` → zmień na `dataclasses.asdict(obj)`.

### Krok 1c — usuń funkcję

**Plik:** `custom_components/thessla_green_modbus/scanner_device_info.py`

#### SZUKAJ (linie 13-20)
```python
def _compat_asdict(obj: Any) -> dict[str, Any]:
    """Use scanner_core.asdict when available (test patch compatibility)."""

    try:
        from . import scanner_core as _scanner_core

        return _scanner_core.asdict(obj)
    except (ImportError, AttributeError, TypeError):  # pragma: no cover - fallback
        return dataclasses.asdict(obj)
```

#### USUŃ (całość)

### Krok 1d — napraw testy (jeśli były)

Jeśli jakieś testy patchowały `scanner_core.asdict`:
```python
# Było:
monkeypatch.setattr("custom_components.thessla_green_modbus.scanner_core.asdict", mock_asdict)

# Ma być:
monkeypatch.setattr("custom_components.thessla_green_modbus.scanner_device_info.dataclasses.asdict", mock_asdict)
# lub po prostu usunąć patch — dataclasses.asdict nie wymaga mockowania.
```

### Oczekiwany efekt
- -8 linii w `scanner_device_info.py`.
- Bezpośrednie wywołanie `dataclasses.asdict` zamiast przez shim.
- Jedna mniej miejsca gdzie produkcja importuje `scanner_core` (shim).

---

## Fix #2 — Usuń `inspect.signature` filtering kwargs w `__init__.py`

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 274-283):**
```python
    try:
        signature = inspect.signature(ThesslaGreenModbusCoordinator)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and not any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    ):
        coordinator_kwargs = {
            key: value for key, value in coordinator_kwargs.items() if key in signature.parameters
        }

    return ThesslaGreenModbusCoordinator(**coordinator_kwargs)
```

**Co to robi:** przed wywołaniem `ThesslaGreenModbusCoordinator(**kwargs)` inspektuje signature klasy i **filtruje `coordinator_kwargs`** do tylko tych parametrów które klasa akceptuje. **Produkcyjny coordinator zawsze akceptuje ten sam zestaw 23 kwargs** — ten filter nigdy nic nie robi w runtime.

**Kiedy filter coś robi:** gdy test podstawił `ThesslaGreenModbusCoordinator` jako coś innego (MagicMock, SimpleNamespace, klasa z mniejszą listą parametrów). Defense przeciw testowym stubom.

**Ryzyko usunięcia:** niskie. Jeśli test zrobi `coordinator_module.ThesslaGreenModbusCoordinator = FakeCoordinator(fewer_params)`, po fixie dostanie `TypeError: unexpected keyword argument 'baud_rate'` zamiast cichego pominięcia. **To lepsze** — test widzi że stub jest niekompletny, zamiast przechodzić z zignorowanymi kwargs.

### Krok 2 — usuń filter

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

#### SZUKAJ (linie 274-285)
```python
    try:
        signature = inspect.signature(ThesslaGreenModbusCoordinator)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and not any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    ):
        coordinator_kwargs = {
            key: value for key, value in coordinator_kwargs.items() if key in signature.parameters
        }

    return ThesslaGreenModbusCoordinator(**coordinator_kwargs)
```

#### ZASTĄP
```python
    return ThesslaGreenModbusCoordinator(**coordinator_kwargs)
```

### Krok 2b — usuń `import inspect` jeśli nie używany gdzie indziej

```bash
grep -n "\binspect\." custom_components/thessla_green_modbus/__init__.py
```

Jeśli `inspect` używany tylko w usuniętym bloku — usuń `import inspect` z nagłówka.

### Krok 2c — napraw testy

```bash
grep -rn "ThesslaGreenModbusCoordinator =\|coordinator_module\.ThesslaGreenModbusCoordinator" tests/ --include="*.py"
```

Każdy test który podstawiał nie-kompletny coordinator — przepisz używając `MagicMock(spec=ThesslaGreenModbusCoordinator)`.

### Oczekiwany efekt
- -12 linii.
- Jeden mniej `inspect.signature` sprawdzenia w produkcji.
- Testy z niekompletnymi stubami zaczną padać jawnie (zamiast cicho pomijać kwargs).

---

## Fix #3 — Usuń `sys.modules.get()` check przed importem coordinator

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 238-247):**
```python
    _coordinator_key = f"{__name__}.coordinator"
    coordinator_mod = sys.modules.get(_coordinator_key)
    if coordinator_mod is None:
        if hasattr(hass, "async_add_executor_job"):
            coordinator_mod = await hass.async_add_executor_job(
                import_module, ".coordinator", __name__
            )
        else:
            coordinator_mod = import_module(".coordinator", __name__)
    ThesslaGreenModbusCoordinator = coordinator_mod.ThesslaGreenModbusCoordinator
```

**Co to robi:** najpierw sprawdza `sys.modules` czy coordinator już był zaimportowany (co daje testom szansę podstawić `sys.modules["...coordinator"] = MockCoordinatorModule`), potem robi executor-import przez HA lub synchroniczny `import_module` jako fallback.

**Smell:**
1. Sprawdzanie `sys.modules` żeby testy mogły patchować — wciąż produkcja-pod-testy.
2. `hasattr(hass, "async_add_executor_job")` — w produkcji zawsze jest, fallback dla stubów HA.

### Krok 3 — uprość import

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

#### SZUKAJ (linie 238-247)
```python
    _coordinator_key = f"{__name__}.coordinator"
    coordinator_mod = sys.modules.get(_coordinator_key)
    if coordinator_mod is None:
        if hasattr(hass, "async_add_executor_job"):
            coordinator_mod = await hass.async_add_executor_job(
                import_module, ".coordinator", __name__
            )
        else:
            coordinator_mod = import_module(".coordinator", __name__)
    ThesslaGreenModbusCoordinator = coordinator_mod.ThesslaGreenModbusCoordinator
```

#### ZASTĄP
```python
    coordinator_mod = await hass.async_add_executor_job(
        import_module, ".coordinator", __name__
    )
    ThesslaGreenModbusCoordinator = coordinator_mod.ThesslaGreenModbusCoordinator
```

### Krok 3b — rozważ przeniesienie importu na top of file

Dynamic import coordynatora przy każdym setup'ie to kosztowne. Jeśli `coordinator` nie powoduje circular import w top-level:

```bash
# Sprawdź czy coordinator.py importuje __init__.py cokolwiek:
grep -n "from \. import\|from \.__init__\|import __init__" custom_components/thessla_green_modbus/coordinator.py
```

Jeśli nie ma cyklu — przenieś na top:
```python
from .coordinator import ThesslaGreenModbusCoordinator
```

Usuń dynamic import z funkcji `_async_create_coordinator`. Prawdopodobnie dynamic import istnieje tylko żeby uniknąć blockującego I/O w setup, ale `import_module` na module Python który jest już w PYTHONPATH nie blokuje (poza pierwszym razem, gdy kompiluje .pyc).

**Jeśli** circular import występuje — zostaw dynamic import, ale bez `sys.modules.get()` check'a.

### Krok 3c — napraw testy

```bash
grep -rn "sys\.modules\[.*coordinator.*\]" tests/ --include="*.py"
```

Jeśli testy robiły `sys.modules["custom_components.thessla_green_modbus.coordinator"] = mock_module` — przepisz używając `monkeypatch.setattr(coordinator_module, "ThesslaGreenModbusCoordinator", MockCoordinator)` lub podobnie.

### Oczekiwany efekt
- -8 linii z defensywnego kodu.
- Szybszy setup (jeśli top-level import — import raz, nie co każdy setup).
- Brak `sys.modules.get()` sprawdzenia jako hook dla testów.

---

## Fix #4 — Usuń `"Skipping in mock context"` try/except w `__init__.py`

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 361-369):**
```python
async def _async_setup_mappings(hass: HomeAssistant) -> None:  # pragma: no cover
    """Load option lists and entity mappings."""
    try:
        await async_setup_options(hass)
    except (TypeError, AttributeError):
        _LOGGER.debug("Skipping async_setup_options in mock context")
    try:
        await async_setup_entity_mappings(hass)
    except (TypeError, AttributeError):
        _LOGGER.debug("Skipping async_setup_entity_mappings in mock context")
```

**Co to robi:** wywołuje `async_setup_options(hass)` — jeśli rzuci `TypeError` lub `AttributeError` (co w produkcji **nie powinno się zdarzyć**), cicho pomija. Komentarz: *"in mock context"* — produkcja wie że może być testowana.

**Dlaczego to jest złe:** jeśli pewnego dnia `async_setup_options` naprawdę rzuci `TypeError` z powodu buga, produkcja go **połknie** bez wyrzucenia setup error. Integracja uruchomi się bez załadowanych option lists, entities będą niekompletne — a użytkownik nie zobaczy błędu.

### Krok 4 — usuń try/except

#### SZUKAJ (linie 361-369)
```python
async def _async_setup_mappings(hass: HomeAssistant) -> None:  # pragma: no cover
    """Load option lists and entity mappings."""
    try:
        await async_setup_options(hass)
    except (TypeError, AttributeError):
        _LOGGER.debug("Skipping async_setup_options in mock context")
    try:
        await async_setup_entity_mappings(hass)
    except (TypeError, AttributeError):
        _LOGGER.debug("Skipping async_setup_entity_mappings in mock context")
```

#### ZASTĄP
```python
async def _async_setup_mappings(hass: HomeAssistant) -> None:  # pragma: no cover
    """Load option lists and entity mappings."""
    await async_setup_options(hass)
    await async_setup_entity_mappings(hass)
```

### Krok 4b — napraw testy

Jeśli testy mockują `hass` jako SimpleNamespace i `async_setup_options(hass)` rzuca `TypeError`:

```python
# Źle - polega na produkcji żeby łapać TypeError:
hass = SimpleNamespace(data={}, ...)
await async_setup_entry(hass, entry)

# Dobrze - użyj pytest-homeassistant-custom-component:
from pytest_homeassistant_custom_component.common import MockConfigEntry
async def test_setup(hass):  # hass fixture z PHCC
    entry = MockConfigEntry(...)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
```

### Oczekiwany efekt
- -4 linie w produkcji.
- Bugs w `async_setup_options` / `async_setup_entity_mappings` nie są już połykane.
- Testy z niepełnymi mock-hass zaczną padać — użyj prawdziwego `hass` fixture.

---

## Fix #5 — Usuń `_HAS_HA` + `"pytest" in sys.modules` w `const.py`

**Plik:** `custom_components/thessla_green_modbus/const.py`

**Dowód (linie 538-545):**
```python
try:  # pragma: no cover - handle partially initialized module
    _HAS_HA = importlib.util.find_spec("homeassistant") is not None
except (ImportError, ValueError):
    _HAS_HA = False

# Load option lists immediately when Home Assistant isn't available or during tests
if not _HAS_HA or "pytest" in sys.modules:  # pragma: no cover - test env
    _sync_setup_options()
```

**To jest KONCEPTUALNIE NAJGORSZY SMELL.** Produkcja:
1. Sprawdza czy Home Assistant jest zainstalowany (co zawsze jest w produkcji — manifest wymaga HA 2026.1.0).
2. Sprawdza czy `pytest` jest w `sys.modules` — czyli **czy kod jest uruchamiany przez pytest**.
3. Na tej podstawie wybiera inną ścieżkę inicjalizacji (`_sync_setup_options()`).

**Kod w produkcji i kod w testach to nie jest ten sam kod.** Produkcja używa async setup (`async_setup_options(hass)`), testy używają sync setup. To znaczy że **testy testują inny kod niż produkcja**.

### Krok 5 — usuń detekcję testów

**Plik:** `custom_components/thessla_green_modbus/const.py`

#### SZUKAJ (linie 538-545)
```python
try:  # pragma: no cover - handle partially initialized module
    _HAS_HA = importlib.util.find_spec("homeassistant") is not None
except (ImportError, ValueError):
    _HAS_HA = False

# Load option lists immediately when Home Assistant isn't available or during tests
if not _HAS_HA or "pytest" in sys.modules:  # pragma: no cover - test env
    _sync_setup_options()
```

#### USUŃ (całość)

### Krok 5b — sprawdź zależności

```bash
# Czy _HAS_HA jest używany gdzie indziej?
grep -rn "_HAS_HA" custom_components/ tests/ --include="*.py"

# Czy _sync_setup_options jest nadal potrzebny?
grep -rn "_sync_setup_options" custom_components/ tests/ --include="*.py"
```

Jeśli `_HAS_HA` nie używany nigdzie indziej — usuń też `import importlib.util`.

Jeśli `_sync_setup_options` używane tylko w tym usuniętym bloku — usuń też funkcję.

### Krok 5c — napraw testy

```bash
grep -rn "_sync_setup_options\|pytest.*sys.modules" tests/ --include="*.py"
```

Testy które polegały na sync setup (bo produkcja to wywoływała automatycznie dla pytest):
```python
# Dodaj explicit wywołanie w fixture:
@pytest.fixture(autouse=True)
async def setup_options(hass):
    from custom_components.thessla_green_modbus.const import async_setup_options
    await async_setup_options(hass)
```

Lub użyj `pytest-homeassistant-custom-component` `hass` fixture który dostarcza pełny HA context.

### Oczekiwany efekt
- -8 linii + potencjalnie `_sync_setup_options` (jeśli tylko dla tego użyty).
- **Produkcja i testy uruchamiają ten sam kod.**
- Brak wykrywania pytest w `sys.modules`.

---

## Fix #6 — Uprość `_create_scanner` w `coordinator.py`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód (linie 448-462):**
```python
    async def _create_scanner(self) -> Any:  # pragma: no cover
        """Instantiate a ThesslaGreenDeviceScanner using the appropriate factory."""
        scanner_cls = getattr(
            import_module(__name__), "ThesslaGreenDeviceScanner", ThesslaGreenDeviceScanner
        )
        kwargs = self._build_scanner_kwargs()
        if not inspect.isclass(scanner_cls):
            return scanner_cls(**kwargs)
        scanner_factory = getattr(scanner_cls, "create", None)
        if callable(scanner_factory):
            result = scanner_factory(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result
        return scanner_cls(**kwargs)
```

**Co to robi:** `import_module(__name__)` = ponowny import `coordinator` module. Potem `getattr(..., "ThesslaGreenDeviceScanner", ThesslaGreenDeviceScanner)` — **pobierz z modułu, a jeśli nie ma → użyj globalnie zaimportowanego**. Standard Python: globalny import i `getattr(module, name, default)` zwracają **dokładnie to samo** poza przypadkiem gdy test patchował moduł.

**Plus:** `if not inspect.isclass(scanner_cls): return scanner_cls(**kwargs)` — defensive check dla przypadku gdy `ThesslaGreenDeviceScanner` został podstawiony jako function/callable zamiast class.

**Wszystko to dla testów.** Produkcyjny `ThesslaGreenDeviceScanner` to klasa z `.create()` factory.

### Krok 6 — uprość

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

#### SZUKAJ (linie 448-462)
```python
    async def _create_scanner(self) -> Any:  # pragma: no cover
        """Instantiate a ThesslaGreenDeviceScanner using the appropriate factory."""
        scanner_cls = getattr(
            import_module(__name__), "ThesslaGreenDeviceScanner", ThesslaGreenDeviceScanner
        )
        kwargs = self._build_scanner_kwargs()
        if not inspect.isclass(scanner_cls):
            return scanner_cls(**kwargs)
        scanner_factory = getattr(scanner_cls, "create", None)
        if callable(scanner_factory):
            result = scanner_factory(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result
        return scanner_cls(**kwargs)
```

#### ZASTĄP
```python
    async def _create_scanner(self) -> Any:  # pragma: no cover
        """Instantiate a ThesslaGreenDeviceScanner using its create() factory."""
        kwargs = self._build_scanner_kwargs()
        return await ThesslaGreenDeviceScanner.create(**kwargs)
```

### Krok 6b — sprawdź zależności

```bash
# Czy import_module i inspect jeszcze używane?
grep -n "\bimport_module\b\|\binspect\." custom_components/thessla_green_modbus/coordinator.py
```

Jeśli nie — usuń `from importlib import import_module` i `import inspect` z nagłówka.

### Krok 6c — napraw testy

Testy które patchowały `coordinator.ThesslaGreenDeviceScanner`:
```python
# Było (działało dzięki dynamic import):
monkeypatch.setattr(
    "custom_components.thessla_green_modbus.coordinator.ThesslaGreenDeviceScanner",
    MockScanner
)

# Wciąż działa:
# monkeypatch.setattr dla stringa modyfikuje atrybut modułu, 
# i ThesslaGreenDeviceScanner w `_create_scanner` odwołuje się do tego atrybutu
# ZAŁOŻENIE: use `coordinator.ThesslaGreenDeviceScanner` reference, nie lokalnej zmiennej
```

**Ważne:** po fixie `ThesslaGreenDeviceScanner.create(...)` używa globalnie zaimportowanego symbolu. Jeśli test patchował tylko `coordinator_module.ThesslaGreenDeviceScanner` (symbol w module), **patch nadal działa** bo Python resolve'uje atrybut przy wywołaniu. Ale jeśli test patchował przez `sys.modules` hack — przepisz.

```bash
grep -rn "coordinator.*ThesslaGreenDeviceScanner" tests/ --include="*.py" | head -10
```

### Oczekiwany efekt
- -10 linii dynamic import madness.
- Bezpośrednia czytelna metoda.
- Mniej indirekcji — łatwiejsza lokalizacja bugów.

---

## Fix #7 — Usuń `inspect.signature(write_cb)` w `entity.py`

**Plik:** `custom_components/thessla_green_modbus/entity.py`

**Dowód (linie 110-124):**
```python
    async def _async_write_register(
        self,
        register_name: str,
        value: int,
        refresh: bool = True,
        offset: int = 0,
        include_offset: bool = False,
    ) -> None:
        """Write a register via coordinator with broad compatibility."""
        write_cb = self.coordinator.async_write_register
        kwargs: dict[str, Any] = {"refresh": False}
        try:
            signature = inspect.signature(write_cb)
        except (TypeError, ValueError):
            signature = None
        if (include_offset or offset != 0) and (
            signature is None
            or "offset" in signature.parameters
            or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())
        ):
            kwargs["offset"] = offset

        success = await write_cb(register_name, value, **kwargs)
```

**Co to robi:** sprawdza czy `coordinator.async_write_register` akceptuje parametr `offset`. Jeśli tak — dodaje do kwargs. Jeśli nie — pomija.

**Kiedy to było potrzebne:** jeśli `async_write_register` historycznie nie miał `offset` i dodany został później, ale nie wszystkie istniejące instances coordinatora zostały zaktualizowane. Dzisiaj wszystkie versions `async_write_register` akceptują `offset`.

**Weryfikacja:**
```bash
# Sprawdź signature produkcyjnej metody:
grep -A 10 "def async_write_register" custom_components/thessla_green_modbus/coordinator.py | head -15
```

Jeśli `async_write_register` ma `offset: int = 0` — filter jest bezużyteczny.

### Krok 7 — uprość

**Plik:** `custom_components/thessla_green_modbus/entity.py`

#### SZUKAJ (linie 108-128)
```python
    async def _async_write_register(
        self,
        register_name: str,
        value: int,
        refresh: bool = True,
        offset: int = 0,
        include_offset: bool = False,
    ) -> None:
        """Write a register via coordinator with broad compatibility."""
        write_cb = self.coordinator.async_write_register
        kwargs: dict[str, Any] = {"refresh": False}
        try:
            signature = inspect.signature(write_cb)
        except (TypeError, ValueError):
            signature = None
        if (include_offset or offset != 0) and (
            signature is None
            or "offset" in signature.parameters
            or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())
        ):
            kwargs["offset"] = offset

        success = await write_cb(register_name, value, **kwargs)
        if not success:
            raise RuntimeError(f"Failed to write register {register_name}")
        if refresh:
            await self.coordinator.async_request_refresh()
```

#### ZASTĄP
```python
    async def _async_write_register(
        self,
        register_name: str,
        value: int,
        refresh: bool = True,
        offset: int = 0,
        include_offset: bool = False,
    ) -> None:
        """Write a register via the coordinator."""
        kwargs: dict[str, Any] = {"refresh": False}
        if include_offset or offset != 0:
            kwargs["offset"] = offset

        success = await self.coordinator.async_write_register(
            register_name, value, **kwargs
        )
        if not success:
            raise RuntimeError(f"Failed to write register {register_name}")
        if refresh:
            await self.coordinator.async_request_refresh()
```

### Krok 7b — sprawdź import `inspect`

```bash
grep -n "\binspect\." custom_components/thessla_green_modbus/entity.py
```

Jeśli nie używane — usuń `import inspect` z nagłówka.

### Krok 7c — napraw testy

Testy które mockowały coordinator z `async_write_register` bez `offset` parameter:

```python
# Było (działało dzięki entity.py filter):
mock_coordinator.async_write_register = AsyncMock(
    signature_without_offset  # pseudo-code
)

# Ma być (explicit signature compat):
async def write(register_name, value, *, refresh=True, offset=0):
    # mock behavior
    return True
mock_coordinator.async_write_register = write
```

Lub użyj `MagicMock(spec=ThesslaGreenModbusCoordinator)` — automatycznie dostaje prawdziwą signature.

### Oczekiwany efekt
- -10 linii defensywnego kodu.
- Bezpośrednie wywołanie bez introspekcji.
- Jeśli coordynator interface się zmieni — entity.py pada jawnie z `TypeError: unexpected keyword argument 'offset'`, łatwo zidentyfikować problem.

---

## Fix #8 — Usuń trywialne wrappery `_schema`/`_required` w `config_flow.py`

**Plik:** `custom_components/thessla_green_modbus/config_flow.py`

**Dowód (linie 152-157):**
```python
def _schema(definition: Any) -> vol.Schema:
    return vol.Schema(definition)


def _required(schema: Any, **kwargs: Any) -> vol.Required:
    return vol.Required(schema, **kwargs)
```

**Kontekst historyczny:** v7 audit zauważył że te wrappery miały 7-poziomowy fallback dla różnych wersji voluptuous stubów. V7 uprościł je do pojedynczego wywołania `vol.*`. Teraz są **trywialnymi wrapperami bez logiki** — ale wciąż istnieją, co jest nieużyteczną indirekcją.

**Użycia:**
```
config_flow.py:700     _required(
config_flow.py:724     _required(CONF_SLAVE_ID, default=slave_default): ...
config_flow.py:747     _required(CONF_HOST, default=host_default): ...
config_flow.py:748     _required(CONF_PORT, default=port_default): ...
config_flow.py:756     _required(CONF_SERIAL_PORT, ...)
config_flow.py:757     _required(CONF_BAUD_RATE, ...)
config_flow.py:758     _required(CONF_PARITY, ...)
config_flow.py:759     _required(CONF_STOP_BITS, ...)
config_flow.py:763     return _schema(data_schema)
config_flow.py:1241    data_schema = _schema(...)
```

14 wywołań łącznie. Zamiana na `vol.Schema` / `vol.Required` to prosta find-replace operacja.

### Krok 8a — zamień wywołania

W `config_flow.py`:

```bash
# Znajdź wszystkie wystąpienia:
grep -n "_schema(\|_required(" custom_components/thessla_green_modbus/config_flow.py
```

**Dla każdej linii:**
- `_schema(definition)` → `vol.Schema(definition)`
- `_required(key, default=...)` → `vol.Required(key, default=...)`
- `_required(CONF_X)` → `vol.Required(CONF_X)`

### Krok 8b — usuń funkcje helper

#### SZUKAJ (linie 152-157)
```python
def _schema(definition: Any) -> vol.Schema:
    return vol.Schema(definition)


def _required(schema: Any, **kwargs: Any) -> vol.Required:
    return vol.Required(schema, **kwargs)
```

#### USUŃ (całość)

### Krok 8c — napraw testy

```bash
grep -rn "_schema\|_required" tests/test_config_flow.py | head -5
```

Testy prawdopodobnie nie używają tych funkcji bezpośrednio. Jeśli używają — zamień na `vol.*`.

### Oczekiwany efekt
- -6 linii (2 funkcje × 3 linie).
- -14 wywołań przez nieużyteczny wrapper.
- `config_flow.py` używa standardowego API voluptuous bezpośrednio.

---

## Weryfikacja końcowa

Po zastosowaniu Fixów #1-#8:

```bash
# Expected: "All checks passed!"
ruff check custom_components/ tests/ tools/

# Expected: "Success: no issues found in ~50 source files"
mypy custom_components/thessla_green_modbus/

# Expected: wszystkie testy przechodzą (ewentualnie po refactorze kilku testów)
pytest tests/ -x -q

# Expected: nadal działa (sprawdza airpack4_modbus.json)
python tools/compare_registers_with_reference.py
```

**Docelowe metryki:**

```
                                  v2.4.0       v2.4.1 (target)
sys.modules check / detection:      2            0  (minus scanner_core shim który zostaje)
"pytest" in sys.modules checks:     1            0
inspect.signature w produkcji:      3            0
# pragma: no cover w __init__.py:  19           15  (−4 z usuniętego kodu)
# pragma: no cover w coordinator:  17           14  (−3)
_compat_asdict w scanner_device:    1            0
Trywialne wrappers w config_flow:   2            0
Linie kodu produkcji:            ~12800      ~12750  (−50)
Test suite pass rate:            100%         100%
```

---

## Bump wersji i CHANGELOG

**Plik:** `custom_components/thessla_green_modbus/manifest.json`
```json
"version": "2.4.1",
```

**Plik:** `pyproject.toml`
```toml
version = "2.4.1"
```

**Plik:** `CHANGELOG.md` — dodaj na górze:
```markdown
## 2.4.1 — Detox completion

Completes the test-compat cleanup started in 2.4.0. Eight remaining spots where
production code tested for or worked around test mocks have been removed.

### Removed
- `_compat_asdict` wrapper in `scanner_device_info.py` that existed for test-patch compatibility. Callers now use `dataclasses.asdict` directly.
- `inspect.signature` filtering of coordinator kwargs in `__init__.py`. Incomplete coordinator stubs will now raise `TypeError` explicitly instead of silently dropping kwargs.
- `sys.modules.get()` check before dynamic coordinator import in `__init__.py`. Module import goes straight through HA executor.
- `try/except TypeError` around `async_setup_options` / `async_setup_entity_mappings` in `_async_setup_mappings`. Real bugs in option setup will no longer be masked by "Skipping in mock context" debug logs.
- `_HAS_HA` detection and `"pytest" in sys.modules` check in `const.py`. Production and test paths now execute identical code.
- Dynamic self-import via `import_module(__name__)` in `coordinator._create_scanner`. Direct reference to `ThesslaGreenDeviceScanner.create()` is used.
- `inspect.signature(write_cb)` check in `entity._async_write_register`. Direct call to `coordinator.async_write_register` with explicit kwargs.
- Trivial `_schema` and `_required` wrappers in `config_flow.py`. Direct `vol.Schema` / `vol.Required` calls used throughout.

### Migration notes
- Tests that relied on production silently filtering kwargs or falling back to sync option setup may need to use `MagicMock(spec=...)` or `pytest-homeassistant-custom-component` fixtures.
- `scanner_core.asdict` is no longer used internally — patching it in tests no longer has any effect.
```

---

## Notatki końcowe

**Dlaczego to minor bump (2.4.1) a nie major (2.5.0):**
- Fixy są czysto removalami test-compat warstwy — zero nowej funkcjonalności.
- Użytkownik końcowy nie widzi różnicy.
- Testy mogą wymagać drobnych zmian, ale bez poważnego przepisywania jak v7.

**Ryzyko regresu — niskie:**
- Każdy fix removuje kod który w produkcji nigdy nie był osiągany (bo produkcja zawsze ma HA i pełne API).
- Testy mogą zacząć padać — **to pożądane**. Każdy padający test to test który dotychczas przechodził z powodu maskującej produkcji, nie prawdziwej poprawności.
- Strategia naprawy testów: `MagicMock(spec=ThesslaGreenModbusCoordinator)` lub `pytest-homeassistant-custom-component` fixtures.

**Grupa B — odłożone architekturalne (nie w tym release):**

Po wdrożeniu v2.4.1 rozważyć w osobnych PR-ach:

1. **Fix #9 — `CoordinatorConfig` dataclass.** 24 parametry w `__init__` kandydują do:
   ```python
   @dataclass
   class CoordinatorConfig:
       host: str
       port: int
       slave_id: int
       # ... pozostałe
       
       @classmethod
       def from_entry(cls, entry: ConfigEntry) -> CoordinatorConfig:
           # ... parsing logic
   
   class ThesslaGreenModbusCoordinator:
       def __init__(self, hass: HomeAssistant, config: CoordinatorConfig, entry: ConfigEntry | None = None):
           ...
   ```
   Wymaga aktualizacji ~10 miejsc konstruujących coordinator w testach. Zmienia publiczny interfejs klasy — major bump (2.5.0).

2. **Fix #10 — Split `scanner/core.py` (1596 linii).** Kontynuacja refactoru z v2.3.6–v2.3.9. Pozostałe duże metody: `verify_connection` (>125 linii), `_run_full_scan`, `scan_device`. Propozycja: `scanner/setup.py` (connection), `scanner/orchestration.py` (scan logic).

3. **Fix #11 — Split `__init__.py` (1067 linii).** 13+ async funkcji w jednym pliku (setup, unload, options, migrations, legacy cleanup, platforms). Propozycja podziału:
   - `__init__.py` — tylko `async_setup_entry`, `async_unload_entry`, `async_update_options`, `async_migrate_entry` (public HA API)
   - `_setup.py` — `_async_create_coordinator`, `_async_start_coordinator`, `_async_setup_mappings`, `_async_setup_platforms`
   - `_migrations.py` — `_async_migrate_unique_ids`, `_async_migrate_entity_ids`, `_async_cleanup_legacy_fan_entity`

4. **Fix #12 — Dalsza redukcja `# pragma: no cover` w `config_flow.py`** (46 nadal obecnych). Po v7 i Fix #8 z tego release część powinna zniknąć. Pozostałe to testy które nie pokrywają path-ów walidacji schematu.

**Priorytet Fix #9-#12:** możliwość zrobienia osobnych PR-ów w tempie właściciela. Każdy jest niezależny.

---

## Podsumowanie metryk po całej serii audytów

```
                          v2.3.0        v2.4.0        v2.4.1 (target)
Mypy errors:               343           0             0
Ruff findings:              7            0             0
Linie produkcji:         ~14500       ~13100        ~12750
_compat.py:                144          75            75
test-compat kod:          ~400         ~50           ~5
sys.modules hacks:          4            1             1 (scanner_core shim)
Klasy istniejące dla testów:  ~10      0             0
# pragma: no cover (total): ~350      302           290
```

Od v2.3.0 do v2.4.1 integracja schudła o **~1750 linii**, przy zachowaniu identycznej funkcjonalności dla użytkowników.
