# thessla_green_modbus — instrukcja napraw dla Claude Code (v6)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main` (HEAD: `58a81af` — merge PR #1327)
**Wersja docelowa:** `2.3.9 → 2.4.0` (major, bo dotyka publicznego API)
**Data audytu:** 2026-04-17

---

## Motywacja: odtrucie produkcji od testów

Wszystkie wersje do 2.3.9 celowały w jakość typów, lint, refactor struktury. Baseline jest czysty (ruff 0, mypy 0). Ale pod powierzchnią siedzi **fundamentalny problem architektoniczny**:

**Produkcja została wygięta żeby dopasować się do źle napisanych testów.**

Audyt znalazł 13 miejsc gdzie production code robi rzeczy których **nigdy nie wykona w runtime**, tylko po to żeby testy używające SimpleNamespace / ręcznie napisanych stubów / niekompletnych mocków działały. To się objawia:

- `sys.modules` manipulation w runtime (2 miejsca)
- Import-time monkey-patching biblioteki voluptuous
- Skanowanie `sys.modules` w poszukiwaniu plików testowych (`tests.conftest`, `tests.test_coordinator`)
- Porównanie typów przez `__class__.__name__ == "UpdateFailed"` zamiast `isinstance`
- `except BaseException` z komentarzem *"Deliberately broad for test stubs"*
- `_PermissiveCapabilities` który zwraca `True` dla każdego atrybutu — i jest **wstawiany do coordynatora w produkcji**
- `_SafeDTUtil` defensywny wrapper na `dt_util` który HA gwarantuje
- 67× `# pragma: no cover` w `config_flow.py` na kodzie który istnieje wyłącznie dla test envs
- `super().__init__()` bez argumentów w fallback bloku `TypeError` — dla stubów które nie przyjmują argumentów HA

**Koszt:** ~500-800 linii kodu produkcyjnego który nie służy użytkownikom, utrudnia czytanie, generuje `# pragma: no cover`, i co gorsza **maskuje prawdziwe błędy**. `except BaseException` z `exc.__class__.__name__ == "UpdateFailed"` oznacza że prawdziwe bugi mogą być połknięte i raportowane jako "connection failed".

**Korzyść z fixa:** mniejszy codebase, testy oparte na HA-provided mocks (`pytest-homeassistant-custom-component` jest w `requirements-dev.txt`), większa pewność że kod działa zgodnie z tym co widać.

**To jest major release** (2.4.0, nie 2.3.10) bo:
- Niektóre fixy usuwają publiczne funkcje (`_update_failed_exception` jest bez `_` — półprywatna).
- Testy wymagają przepisania na `pytest-homeassistant-custom-component`.
- Potencjalny breaking change dla zewnętrznych narzędzi (mało prawdopodobnych, ale formalnie).

---

## Zakres i kolejność

| Fix | Smell | Ryzyko | Trudność |
|---|---|---|---|
| #1 | `_update_failed_exception` skanuje sys.modules testów | Wysokie zanim, niskie potem | Średnia |
| #2 | `__init__.py` alias dla testów patchujących `__init__.er` | Średnie | Niska |
| #3 | `entity_mappings.py` to `sys.modules[__name__] = _m` | Niskie | Niska |
| #4 | `_async_patch_coordinator_compat` + `_PermissiveCapabilities` w produkcji | Wysokie | Średnia |
| #5 | `_SafeDTUtil` defensywny wrapper na `dt_util` | Niskie | Niska |
| #6 | `super().__init__()` TypeError fallback w coordinator | Niskie | Niska |
| #7 | `config_flow.py` test-compat layer (67× `# pragma: no cover`) | Wysokie | **Duża** |
| #8 | `except BaseException` + `__class__.__name__` w `__init__.py` | Wysokie | Średnia |
| #9 | Legacy migracje v1→v4 — czy v1 jeszcze istnieje? | Średnie | Niska |
| #10 | Defensywne `getattr` w krytycznych ścieżkach | Średnie | Średnia |

**Wykonanie w kolejności 1→10.** Każdy fix robi test-suite:

```bash
ruff check custom_components/ tests/ tools/
mypy custom_components/thessla_green_modbus/
pytest tests/ -x -q
```

**Jeśli po danym fixie testy padają** — to jest sygnał że test polega na smell'u. Przepisz test, nie cofaj fixa.

---

## Fix #1 — Usuń `_update_failed_exception`, używaj `UpdateFailed` wszędzie

**Plik:** `custom_components/thessla_green_modbus/coordinator.py` (+ callers)

**Dowód problemu (linie 134-148):**
```python
def _update_failed_exception(message: str) -> Exception:
    """Return an UpdateFailed compatible with patched test helper modules."""

    classes: list[type[Exception]] = [UpdateFailed]
    for mod_name in ("tests.conftest", "tests.test_coordinator", "tests.test_services"):
        mod = sys.modules.get(mod_name)
        cls = getattr(mod, "UpdateFailed", None) if mod is not None else None
        if isinstance(cls, type) and issubclass(cls, Exception) and cls not in classes:
            classes.append(cls)

    if len(classes) == 1:
        return classes[0](message)  # pragma: no cover

    compat_cls = cast(type[Exception], type("CompatUpdateFailed", tuple(classes), {}))
    return compat_cls(message)
```

**Co to robi:** produkcja szuka `tests/conftest.py`, `tests/test_coordinator.py`, `tests/test_services.py` w `sys.modules`. Jeśli któryś z tych plików testowych zdefiniował **własną** klasę `UpdateFailed` (prawdopodobnie żeby uniknąć importu HA), produkcja tworzy *dynamicznie* klasę dziedziczącą po wszystkich znalezionych, żeby testowe `isinstance(exc, TestUpdateFailed)` zwracało True.

**To jest nieakceptowalne w produkcji.** Coordinator nie powinien nawet wiedzieć że istnieje folder `tests/`.

**Przyczyna:** w jakimś momencie ktoś napisał test który importuje `UpdateFailed` lokalnie zamiast z `homeassistant.helpers.update_coordinator`. Zamiast naprawić test, dodano **jeden z najgorszych hacków w całym codebasie**.

### Krok 1a — usuń funkcję

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

#### SZUKAJ (linie 134-148)
```python
def _update_failed_exception(message: str) -> Exception:
    """Return an UpdateFailed compatible with patched test helper modules."""

    classes: list[type[Exception]] = [UpdateFailed]
    for mod_name in ("tests.conftest", "tests.test_coordinator", "tests.test_services"):
        mod = sys.modules.get(mod_name)
        cls = getattr(mod, "UpdateFailed", None) if mod is not None else None
        if isinstance(cls, type) and issubclass(cls, Exception) and cls not in classes:
            classes.append(cls)

    if len(classes) == 1:
        return classes[0](message)  # pragma: no cover

    compat_cls = cast(type[Exception], type("CompatUpdateFailed", tuple(classes), {}))
    return compat_cls(message)
```

#### USUŃ (całość)

### Krok 1b — zastąp wszystkie wywołania

```bash
grep -rn "_update_failed_exception" custom_components/ tests/ --include="*.py"
```

**W każdym miejscu gdzie występuje `_update_failed_exception(msg)` zastąp przez `UpdateFailed(msg)`.**

W `coordinator.py` prawdopodobnie są to fragmenty w `_handle_update_error` (z poprzedniego audytu) + `_async_update_data`. Upewnij się że `UpdateFailed` jest już zaimportowane z `_compat.py`:
```bash
grep -n "UpdateFailed" custom_components/thessla_green_modbus/coordinator.py | head -5
```

Jeśli brak importu — dodaj:
```python
from ._compat import UpdateFailed
```

### Krok 1c — usuń `cast` import jeśli nieużywany

```bash
grep -n "cast" custom_components/thessla_green_modbus/coordinator.py | head -5
```

Jeśli `cast` był importowany tylko dla `_update_failed_exception`, usuń z importów `from typing import cast`.

### Krok 1d — usuń `sys` jeśli nieużywany

```bash
grep -n "\bsys\." custom_components/thessla_green_modbus/coordinator.py
```

Jeśli tylko w usuniętej funkcji — usuń `import sys`.

### Krok 1e — napraw testy które to wymuszały

Znajdź testy definiujące własny `UpdateFailed`:
```bash
grep -rn "class UpdateFailed\|UpdateFailed = " tests/ --include="*.py"
```

Każdy taki test przepisz żeby używał `homeassistant.helpers.update_coordinator.UpdateFailed` lub `pytest-homeassistant-custom-component` fixtures. Jeśli test mockuje bez HA — dodaj `@pytest.mark.homeassistant` lub użyj `pytest-homeassistant-custom-component` który dostarcza prawdziwy `UpdateFailed`.

### Oczekiwany efekt
- -15 linii najgorszego kodu w codebase.
- Coordinator nie wie o istnieniu `tests/`.
- Jeśli testy zaczną padać: każdy padający test mówi *"I was importing UpdateFailed wrongly"*. Naprawić test.

---

## Fix #2 — Usuń alias `__init__.er` dla testów

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 87-92):**
```python
# Compatibility shim for tests patching "custom_components.thessla_green_modbus.__init__.er".
_init_alias = sys.modules.setdefault(f"{__name__}.__init__", sys.modules[__name__])
_init_alias_any: Any = _init_alias
_init_alias_any.er = er
module_self: Any = sys.modules[__name__]
module_self.__init__ = _init_alias
```

Produkcja rejestruje w `sys.modules` fikcyjny moduł `custom_components.thessla_green_modbus.__init__` (którego Python normalnie **nie tworzy** — `__init__.py` staje się samym pakietem, nie jego submodułem). Potem przypisuje `er` (entity_registry) do tego fikcyjnego modułu, żeby testy mogły robić:
```python
monkeypatch.setattr("custom_components.thessla_green_modbus.__init__.er", mock_er)
```

**Prawidłowy sposób** monkey-patching w pytest to:
```python
monkeypatch.setattr("custom_components.thessla_green_modbus.er", mock_er)
# lub
monkeypatch.setattr(some_module, "er", mock_er)
```

### Krok 2a — usuń alias

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

#### SZUKAJ (linie 87-92)
```python
# Compatibility shim for tests patching "custom_components.thessla_green_modbus.__init__.er".
_init_alias = sys.modules.setdefault(f"{__name__}.__init__", sys.modules[__name__])
_init_alias_any: Any = _init_alias
_init_alias_any.er = er
module_self: Any = sys.modules[__name__]
module_self.__init__ = _init_alias
```

#### USUŃ (całość)

### Krok 2b — napraw testy

```bash
grep -rn "thessla_green_modbus\.__init__\.\|__init__\.er\b" tests/ --include="*.py"
```

Dla każdego znalezionego `monkeypatch.setattr("...__init__.er", ...)` zmień na:
```python
monkeypatch.setattr("custom_components.thessla_green_modbus.er", ...)
```

Lub, jeśli test monkey-patchuje przed importem, użyj `pytest-homeassistant-custom-component` fixtures.

### Oczekiwany efekt
- -6 linii, -1 `sys.modules` hack.
- Testy używają standardowego monkey-patching.

---

## Fix #3 — Usuń `entity_mappings.py` shim

**Plik:** `custom_components/thessla_green_modbus/entity_mappings.py`

**Dowód (całe 37 linii):**
```python
"""Backward-compatible shim for the ``mappings`` package."""

from __future__ import annotations

import sys

from . import mappings as _m
from .mappings import (
    BINARY_SENSOR_ENTITY_MAPPINGS,
    ENTITY_MAPPINGS,
    # ... itd.
)

# Keep ``entity_mappings`` as an alias of ``mappings`` so existing tests and
# monkeypatches that mutate module globals continue to affect runtime behavior.
_m.__file__ = __file__
sys.modules[__name__] = _m
```

**Co to robi:** cały plik istnieje żeby `from .entity_mappings import X` działało identycznie z `from .mappings import X`. Problem — nie przez zwykły re-export, tylko przez **podmianę modułu w sys.modules**. Komentarz wprost: *"so existing tests and monkeypatches that mutate module globals continue to affect runtime behavior"*.

**Konsekwencje obecnego stanu:**
- `entity_mappings` jako moduł **nie istnieje** — `sys.modules["custom_components.thessla_green_modbus.entity_mappings"]` wskazuje na moduł `mappings`.
- Importy w produkcji (`from .entity_mappings import ENTITY_MAPPINGS`) działają przez przypadek — Python cache'uje.
- Testy robiące `monkeypatch.setattr("custom_components.thessla_green_modbus.entity_mappings.ENTITY_MAPPINGS", ...)` modyfikują w rzeczywistości `mappings.ENTITY_MAPPINGS` — bo to ten sam obiekt w sys.modules.

### Krok 3a — zamień wszystkie importy

```bash
grep -rn "from \.entity_mappings\|from \.\.entity_mappings" custom_components/ tests/ --include="*.py"
```

Wyniki (z poprzedniego skanu):
```
register_map.py:173     from .entity_mappings import ENTITY_MAPPINGS
switch.py:19            from .entity_mappings import ENTITY_MAPPINGS
__init__.py:72          from .entity_mappings import async_setup_entity_mappings
const.py:309            from .entity_mappings import ENTITY_MAPPINGS as _MAP
number.py:19            from .entity_mappings import ENTITY_MAPPINGS
time.py:23              from .entity_mappings import ENTITY_MAPPINGS
sensor.py:34            from .entity_mappings import ENTITY_MAPPINGS
binary_sensor.py:26     from .entity_mappings import BINARY_SENSOR_ENTITY_MAPPINGS
text.py:22              from .entity_mappings import ENTITY_MAPPINGS
services.py:32          from .entity_mappings import map_legacy_entity_id
```

**Zamień w każdym:** `from .entity_mappings import X` → `from .mappings import X`

### Krok 3b — usuń plik

```bash
rm custom_components/thessla_green_modbus/entity_mappings.py
```

### Krok 3c — napraw testy

```bash
grep -rn "entity_mappings\b" tests/ --include="*.py"
```

W każdym teście użyj `mappings`:
```python
# Było:
monkeypatch.setattr("custom_components.thessla_green_modbus.entity_mappings.ENTITY_MAPPINGS", ...)
# Ma być:
monkeypatch.setattr("custom_components.thessla_green_modbus.mappings.ENTITY_MAPPINGS", ...)
```

### Oczekiwany efekt
- -37 linii shim.
- -1 `sys.modules` hack.
- Czytelniejsze importy — jedno źródło (`mappings`).

---

## Fix #4 — Usuń `_async_patch_coordinator_compat` + `_PermissiveCapabilities`

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 384-415):**
```python
def _async_patch_coordinator_compat(
    coordinator: Any, entry: ConfigEntry
) -> None:  # pragma: no cover
    """Add lightweight fallback attributes for test environments."""
    if not hasattr(coordinator, "capabilities"):

        class _PermissiveCapabilities:
            def __getattr__(self, _name: str) -> bool:
                return True

        coordinator.capabilities = _PermissiveCapabilities()

    if not hasattr(coordinator, "get_register_map"):
        empty_maps: dict[str, dict[str, Any]] = {
            "input_registers": {},
            "holding_registers": {},
            "coil_registers": {},
            "discrete_inputs": {},
        }
        coordinator.get_register_map = lambda reg_type: empty_maps.get(reg_type, {})

    if not hasattr(coordinator, "available_registers"):
        coordinator.available_registers = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

    force_full = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    if not hasattr(coordinator, "force_full_register_list"):
        coordinator.force_full_register_list = bool(force_full)
```

**Co to robi:** produkcja sprawdza czy coordinator ma kluczowe atrybuty (`capabilities`, `get_register_map`, `available_registers`, `force_full_register_list`) i je dorabia jeśli brak. `_PermissiveCapabilities` **zwraca `True` dla każdego atrybutu** — to oznacza że *"urządzenie ma każdą funkcję"*.

**W produkcji** `ThesslaGreenModbusCoordinator.__init__` **zawsze** ustawia wszystkie te atrybuty. Więc ta funkcja nigdy nic nie robi w runtime. Jest zawsze no-op… chyba że ktoś podstawi coordinator będący SimpleNamespace (test). Wtedy `_PermissiveCapabilities` zaczyna mówić *"true"* na każde zapytanie o capability, co może maskować błędne testy.

### Krok 4a — usuń funkcję

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

#### SZUKAJ (linie 384-415)
```python
def _async_patch_coordinator_compat(
    coordinator: Any, entry: ConfigEntry
) -> None:  # pragma: no cover
    """Add lightweight fallback attributes for test environments."""
    if not hasattr(coordinator, "capabilities"):

        class _PermissiveCapabilities:
            def __getattr__(self, _name: str) -> bool:
                return True

        coordinator.capabilities = _PermissiveCapabilities()

    if not hasattr(coordinator, "get_register_map"):
        empty_maps: dict[str, dict[str, Any]] = {
            "input_registers": {},
            "holding_registers": {},
            "coil_registers": {},
            "discrete_inputs": {},
        }
        coordinator.get_register_map = lambda reg_type: empty_maps.get(reg_type, {})

    if not hasattr(coordinator, "available_registers"):
        coordinator.available_registers = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

    force_full = entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
    if not hasattr(coordinator, "force_full_register_list"):
        coordinator.force_full_register_list = bool(force_full)
```

#### USUŃ (całość)

### Krok 4b — usuń wywołanie

Znajdź wywołanie:
```bash
grep -n "_async_patch_coordinator_compat" custom_components/thessla_green_modbus/__init__.py
```

Powinno być tylko jedno wywołanie (linia 475). Usuń tę linię całkowicie.

### Krok 4c — napraw testy

```bash
grep -rn "_async_patch_coordinator_compat\|_PermissiveCapabilities" tests/ --include="*.py"
```

Jeśli testy referencują tę funkcję — usuń referencje. Jeśli testy polegają na `_PermissiveCapabilities` (SimpleNamespace bez capabilities) — **przepisz test**, użyj prawdziwego coordynatora z `pytest-homeassistant-custom-component`, lub Mock z explicit `capabilities`:

```python
# Źle:
coordinator = SimpleNamespace(host="1.2.3.4", port=502)
# _PermissiveCapabilities ratowało to w produkcji.

# Dobrze:
coordinator = MagicMock()
coordinator.capabilities.basic_control = True
coordinator.available_registers = {...}
# Test explicite mówi czego wymaga.
```

### Oczekiwany efekt
- -35 linii niebezpiecznego kodu.
- Testy jawnie deklarują czego potrzebują od coordynatora.
- Brak ryzyka że test "przypadkiem" pokaże zieloną ścieżkę bo capability wraca True-by-default.

---

## Fix #5 — Usuń `_SafeDTUtil` i `_utcnow` defensive wrappers

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód (linie 84-119):**
```python
class _SafeDTUtil:
    """Wrap dt helpers and always return timezone-aware datetimes."""

    def __init__(self, base: Any) -> None:
        self._base = base

    @staticmethod
    def _coerce(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return datetime.now(UTC)

    def now(self) -> datetime:
        func = getattr(self._base, "now", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)

    def utcnow(self) -> datetime:
        func = getattr(self._base, "utcnow", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)


dt_util = _SafeDTUtil(_base_dt_util)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    utcnow_callable = getattr(dt_util, "utcnow", None)
    if callable(utcnow_callable):
        value = utcnow_callable()
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return datetime.now(UTC)
```

**Co to robi:** `_SafeDTUtil` wrapuje `_base_dt_util` (czyli `homeassistant.util.dt`) defensywnie — każde wywołanie `now()` sprawdza czy `base.now` istnieje, czy jest callable, czy zwraca datetime, czy ma tzinfo. `_utcnow()` z kolei wrapuje już `_SafeDTUtil.utcnow` jeszcze raz, z dokładnie tymi samymi sprawdzeniami.

**Rzeczywistość:** HA `dt_util.utcnow()` **zawsze** zwraca `datetime` z `tzinfo=UTC`. To jest gwarancja od 2022 roku. Te dwa wrapersy istnieją tylko dla testów które mockują `dt_util` byle czym (SimpleNamespace, lambda, None).

### Krok 5a — usuń klasę i wrapper

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

#### SZUKAJ (linie 84-119)
```python
class _SafeDTUtil:
    """Wrap dt helpers and always return timezone-aware datetimes."""

    def __init__(self, base: Any) -> None:
        self._base = base

    @staticmethod
    def _coerce(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return datetime.now(UTC)

    def now(self) -> datetime:
        func = getattr(self._base, "now", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)

    def utcnow(self) -> datetime:
        func = getattr(self._base, "utcnow", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)


dt_util = _SafeDTUtil(_base_dt_util)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    utcnow_callable = getattr(dt_util, "utcnow", None)
    if callable(utcnow_callable):
        value = utcnow_callable()
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return datetime.now(UTC)
```

#### ZASTĄP
```python
# Re-export HA dt util directly. _base_dt_util is imported from ._compat.
dt_util = _base_dt_util


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return dt_util.utcnow()
```

### Krok 5b — sprawdź użycia

```bash
grep -n "dt_util\._base\|_SafeDTUtil" custom_components/ tests/ --include="*.py" -r
```

Usuń wszystkie referencje. Jeśli coś jeszcze polega na `_SafeDTUtil` jako klasie — to test, i powinien używać prawdziwego `dt_util`.

### Oczekiwany efekt
- -36 linii defensywnego kodu.
- Jedna implementacja `dt_util.utcnow()` zamiast trzech.
- Testy które mockowały `dt_util` byle czym zaczynają padać — naprawić używając `freezegun` lub HA `dt_util.utcnow` patching.

---

## Fix #6 — Usuń `super().__init__()` TypeError fallback

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód (linie 195-207):**
```python
        try:
            super().__init__(
                hass,
                _LOGGER,
                name=f"{DOMAIN}_{entry.entry_id if entry else name}",
                update_interval=update_interval,
            )
        except TypeError:
            super().__init__()
            self.hass = hass
            self.logger = _LOGGER
            self.name = f"{DOMAIN}_{entry.entry_id if entry else name}"
            self.update_interval = update_interval
```

**Co to robi:** jeśli `super().__init__()` rzuci `TypeError` (czyli HA `DataUpdateCoordinator.__init__` nie akceptuje tych argumentów — co nigdy nie zdarzy się w produkcji), wywołuje `super().__init__()` bez argumentów i ręcznie przypisuje atrybuty.

**Kiedy to się zdarzyło w historii:** prawdopodobnie ktoś zrobił:
```python
class StubBase:
    def __init__(self):
        pass

ThesslaGreenModbusCoordinator.__bases__ = (StubBase, ...)
```

W teście który nie potrafił zainstalować HA. Zamiast użyć `pytest-homeassistant-custom-component`, coordinator został wygięty.

### Krok 6 — usuń fallback

#### SZUKAJ
```python
        try:
            super().__init__(
                hass,
                _LOGGER,
                name=f"{DOMAIN}_{entry.entry_id if entry else name}",
                update_interval=update_interval,
            )
        except TypeError:
            super().__init__()
            self.hass = hass
            self.logger = _LOGGER
            self.name = f"{DOMAIN}_{entry.entry_id if entry else name}"
            self.update_interval = update_interval
```

#### ZASTĄP
```python
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id if entry else name}",
            update_interval=update_interval,
        )
```

### Oczekiwany efekt
- -8 linii.
- Coordinator ma jeden sposób inicjalizacji.
- Jeśli test pada — używa prawdziwego HA `DataUpdateCoordinator`.

---

## Fix #7 — Wyczyść `config_flow.py` z warstwy test-compat

**Plik:** `custom_components/thessla_green_modbus/config_flow.py` (**Duża zmiana — rozważyć osobny PR**)

**Dowód — wiele miejsc:**

### 7a. DhcpServiceInfo / ZeroconfServiceInfo fallback (linie 24-43)

```python
try:
    from homeassistant.components.dhcp import DhcpServiceInfo
except (ImportError, ModuleNotFoundError):

    @dataclasses.dataclass
    class DhcpServiceInfo:
        """Fallback DHCP service info for minimal test environments."""
        macaddress: str | None = None
        ip: str | None = None
```

**Rozwiązanie — usuń fallback:**
```python
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.zeroconf import ZeroconfServiceInfo
```

### 7b. ConfigFlowResult fallback (linia 46-49)

```python
try:
    from homeassistant.config_entries import ConfigFlowResult
except (ImportError, ModuleNotFoundError):
    ConfigFlowResult = dict[str, Any]
```

**Rozwiązanie:** `ConfigFlowResult` jest w HA od 2023.9. Manifest wymaga 2026.1.0. Zostaw tylko import:
```python
from homeassistant.config_entries import ConfigFlowResult
```

### 7c. `_FallbackFlowBase` (linie 123-142)

```python
class _FallbackFlowBase:  # pragma: no cover
    """Fallback flow base for minimal test environments."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        return None

    async def async_set_unique_id(self, *args: Any, **kwargs: Any) -> None:
        return None

    def _abort_if_unique_id_configured(self) -> None:
        return None

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "abort", **kwargs}
```

**Co to robi:** klasa udaje `ConfigFlow` dla testów które nie chcą HA. **Nie jest nigdzie używana** (sprawdź: `grep _FallbackFlowBase`). Martwy kod.

**Rozwiązanie:** usunąć całą klasę.

### 7d. Monkey-patch voluptuous (linie 175-186)

```python
class _VolInvalid(Exception):
    """Fallback voluptuous Invalid-like exception."""

    def __init__(self, error_message: str, path: list[str] | None = None) -> None:
        super().__init__(error_message)
        self.error_message = error_message
        self.path = path or []


VOL_INVALID = getattr(vol, "Invalid", _VolInvalid)
if not hasattr(vol, "Invalid"):
    vol.Invalid = VOL_INVALID  # pragma: no cover
```

**Co to robi:** **przy imporcie modułu** podmienia `voluptuous.Invalid` jeśli nie istnieje. **Monkey-patch biblioteki**. Voluptuous ma `Invalid` od 2012 roku. `voluptuous>=0.13` jest w `requirements.txt`.

**Rozwiązanie:**
```python
from voluptuous import Invalid as VOL_INVALID
```

Usuń `_VolInvalid` i blok `if not hasattr`.

### 7e. `_schema` dodaje `.schema` atrybut (linie 189-194)

```python
def _schema(definition: Any) -> Any:
    """Create voluptuous schema with `.schema` compatibility for tests."""
    schema_obj = vol.Schema(definition)
    if not hasattr(schema_obj, "schema"):
        schema_obj.schema = definition  # pragma: no cover
    return schema_obj
```

**Co to robi:** voluptuous `Schema` obiekt **ma** atrybut `.schema` (to sam definition). Jeśli test mockuje `vol.Schema = lambda x: SomeMock()`, wtedy mock może nie mieć `.schema`. Produkcja dokleja go ręcznie. Smell.

**Rozwiązanie:**
```python
def _schema(definition: Any) -> vol.Schema:
    return vol.Schema(definition)
```

### 7f. `_required` 7-poziomowy fallback (linie 197-213)

```python
def _required(schema: Any, **kwargs: Any) -> Any:
    """Compat wrapper for voluptuous.Required across test stubs."""
    try:
        return vol.Required(schema, **kwargs)
    except TypeError:  # pragma: no cover
        msg = kwargs.get("msg")  # pragma: no cover
        default = kwargs.get("default", ...)  # pragma: no cover
        description = kwargs.get("description")  # pragma: no cover
        try:  # pragma: no cover
            return vol.Required(schema, msg, default, description)  # pragma: no cover
        except TypeError:  # pragma: no cover
            # ... 3 kolejne poziomy fallbacku
```

**Co to robi:** próbuje wywołać `vol.Required` z różnymi kombinacjami argumentów. Voluptuous `Required(schema, msg=None, default=UNDEFINED, description=None)` — stabilne API od lat.

**Rozwiązanie:**
```python
def _required(schema: Any, **kwargs: Any) -> vol.Required:
    return vol.Required(schema, **kwargs)
```

Lub jeszcze lepiej — usuń funkcję, używaj `vol.Required` bezpośrednio. Sprawdź:
```bash
grep -n "_required(" custom_components/thessla_green_modbus/config_flow.py
```

Jeśli tylko kilka wywołań — zamień na `vol.Required` bez wrappera.

### Krok 7 — wykonanie

Otwórz `config_flow.py` i przeprowadź wszystkie 6 zamian. Po każdej:
```bash
ruff check custom_components/thessla_green_modbus/config_flow.py
mypy custom_components/thessla_green_modbus/config_flow.py
pytest tests/test_config_flow.py -x -q
```

Testy prawdopodobnie będą padały. **Każdy padający test to test który nielegalnie mockuje voluptuous lub HA bez używania `pytest-homeassistant-custom-component`.** Fix test, nie cofaj zmiany.

### Oczekiwany efekt
- -100 do -150 linii, znaczna część z 67 `# pragma: no cover`.
- `config_flow.py` przestaje być chimera produkcja+test-stubs.
- Voluptuous nie jest monkey-patchowany przy imporcie integracji.

---

## Fix #8 — Wywal `except BaseException` + `__class__.__name__` w `__init__.py`

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 322-338 i 363-379, dwa identyczne bloki):**

```python
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt | SystemExit | asyncio.CancelledError):
            raise
        # Deliberately broad at integration setup boundary: Home Assistant test
        # stubs and custom coordinator implementations may raise dynamic
        # exception classes (including test-local subclasses of UpdateFailed).
        # We convert all such failures into ConfigEntryNotReady/reauth flow.
        if (
            isinstance(exc, Exception)
            and (isinstance(exc, UpdateFailed) or exc.__class__.__name__ == "UpdateFailed")
            and is_invalid_auth_error(exc)
        ):
            _LOGGER.error("Authentication failed during setup: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc
```

**Dwa smelle w jednym:**
1. **`except BaseException`** — łapie też niesystemowe BaseException-descendants, ale po `KeyboardInterrupt | SystemExit | CancelledError` zostaje tylko `Exception`. Czyli to powinno być po prostu `except Exception`.
2. **`exc.__class__.__name__ == "UpdateFailed"`** — porównanie klasy po **nazwie stringa**. To jest anti-pattern. Jeśli `isinstance(exc, UpdateFailed)` nie zwraca True, to dlatego że test zdefiniował *własną* klasę `UpdateFailed` (patrz Fix #1). Po usunięciu tego hacka, ten warunek też upada.

### Krok 8 — uprość oba bloki

#### SZUKAJ (linia 322, pierwszy blok)
```python
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt | SystemExit | asyncio.CancelledError):
            raise
        # Deliberately broad at integration setup boundary: Home Assistant test
        # stubs and custom coordinator implementations may raise dynamic
        # exception classes (including test-local subclasses of UpdateFailed).
        # We convert all such failures into ConfigEntryNotReady/reauth flow.
        if (
            isinstance(exc, Exception)
            and (isinstance(exc, UpdateFailed) or exc.__class__.__name__ == "UpdateFailed")
            and is_invalid_auth_error(exc)
        ):
            _LOGGER.error("Authentication failed during setup: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc
```

#### ZASTĄP
```python
    except Exception as exc:
        if isinstance(exc, UpdateFailed) and is_invalid_auth_error(exc):
            _LOGGER.error("Authentication failed during setup: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc
```

**Zrób analogicznie z drugim blokiem (linia 363)** — taka sama struktura.

**Uwaga:** `except Exception` jest dalej szerokie, ale:
- `KeyboardInterrupt`, `SystemExit`, `CancelledError` dziedziczą z `BaseException` (nie `Exception`) — automatycznie wyłączone.
- Nie ma potrzeby ręcznego `isinstance(exc, KeyboardInterrupt | SystemExit | asyncio.CancelledError): raise`.

### Oczekiwany efekt
- -10 linii w każdym bloku, razem -20.
- Czytelniejsza logika.
- Jedno `isinstance(exc, UpdateFailed)` zamiast dualnego check'a z nazwą stringa.

---

## Fix #9 — Audit `async_migrate_entry` (czy v1 jeszcze istnieje?)

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 1052+):**
```python
async def async_migrate_entry(hass, config_entry) -> bool:
    """Migrate old entry.

    Home Assistant uses this during upgrades; vulture marks it as unused but
    the runtime imports it dynamically.
    """
    if config_entry.version == 1:
        # Migrate "unit" to CONF_SLAVE_ID if needed
        # Add CONF_PORT = LEGACY_DEFAULT_PORT = 8899
        # Add CONF_SCAN_INTERVAL, CONF_TIMEOUT, CONF_RETRY defaults
        config_entry.version = 2

    if config_entry.version == 2:
        if CONF_CONNECTION_TYPE not in new_data:
            new_data[CONF_CONNECTION_TYPE] = DEFAULT_CONNECTION_TYPE
        config_entry.version = 3

    if config_entry.version == 3:
        # ... connection_mode normalization
        config_entry.version = 4
    ...
```

**Pytanie:** ile instalacji w świecie jest wciąż na `config_entry.version == 1`? Nie wiadomo. Ale jeśli zero — kod obsługujący migrację v1→v2 jest martwy.

**Sygnaly że v1 to historia:**
- Komentarz wprost: *"older versions relied on legacy default"* — "older" to historia.
- `LEGACY_DEFAULT_PORT = 8899` jest pre-v2.
- HA rekomenduje usuwanie starych migracji po 2-3 wersjach głównych.

### Krok 9a — sprawdź gdzie v1 bywa

```bash
# W testach — czy testy tworzą entries z version == 1?
grep -rn "version.*=.*1\|version=1" tests/ --include="*.py" | grep -i "config_entry\|entry\|version" | head -10
```

### Krok 9b — opcjonalne: usuń gałąź v1

**Decyzja biznesowa:** jeśli Bart zgadza się że po 2+ latach użytkownicy powinni być na v2+, usunąć gałąź `if config_entry.version == 1`. Integracja będzie odmawiać ładowania dla v1, użytkownik musi usunąć i dodać entry od nowa.

**Jeśli nie gotowy:** zostaw migrację, ale usuń komentarz *"vulture marks it as unused"* (Fix nie używa vulture od v2.3.10).

### Krok 9c — zaktualizuj komentarz

```python
async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:  # pragma: no cover
    """Migrate old entry.

    Called by Home Assistant during integration upgrades.
    """
```

### Oczekiwany efekt
- Ewentualnie -40 linii jeśli v1 idzie precz.
- Czytelniejsza dokumentacja.

---

## Fix #10 — Defensywne `getattr` w krytycznych ścieżkach

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`, `__init__.py`

**Dowód (linia 413):**
```python
start_reauth = getattr(self.entry, "async_start_reauth", None)
```

**Co to robi:** sprawdza czy `self.entry` (ConfigEntry) ma metodę `async_start_reauth`. **Ma**, od HA 2023+. Defensywny `getattr` istnieje tylko dla testów z SimpleNamespace.

**Dowód (linie 429, 435):**
```python
transport_method = getattr(transport, name, None) if transport is not None else None
method = getattr(client, name, None) if client is not None else None
```

**Kontekst:** `_get_client_method(name)` pobiera dynamicznie metodę Modbus client. **Tutaj getattr jest uzasadniony** — różne klienty (TCP, RTU, raw-rtu-over-tcp) mają lub nie mają niektórych metod (`read_input_registers` vs `read_holding_registers`). Nie zmieniać.

### Krok 10 — wyczyść `async_start_reauth`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`, linia 413

#### SZUKAJ
```python
        start_reauth = getattr(self.entry, "async_start_reauth", None)
        if callable(start_reauth):
            # ... call it
```

#### ZASTĄP
```python
        if self.entry is not None:
            self.entry.async_start_reauth(self.hass)
```

(zakładając że ten wzorzec jest używany — sprawdź kontekst wokół linii 413).

### Pozostałe getattr — audit

```bash
grep -rn "getattr(.*, None)" custom_components/thessla_green_modbus/ --include="*.py" | grep -v "scanner\|mappings\|_loaders"
```

Dla każdego wystąpienia zadaj pytanie:
- Czy docelowy atrybut istnieje w prawdziwym HA / PyModbus / voluptuous?
- Jeśli tak → `getattr` to smell, usunąć.
- Jeśli nie (np. optional HA component) → zostawić z komentarzem dlaczego.

### Oczekiwany efekt
- -5 do -15 linii zależnie od znalezionych getattr-smelli.
- Każde pozostałe `getattr` ma uzasadnienie.

---

## Weryfikacja po wszystkich Fixach

```bash
# Baseline:
ruff check custom_components/ tests/ tools/     # Expected: All checks passed!
mypy custom_components/thessla_green_modbus/    # Expected: Success

# Testy — tutaj prawdopodobnie będą padały:
pytest tests/ -x -q
```

**Co robić z padającymi testami:**

1. **Test używa SimpleNamespace zamiast HA Mock** → przepisz test na `pytest-homeassistant-custom-component`.
2. **Test definiuje własny UpdateFailed** → użyj `from homeassistant.helpers.update_coordinator import UpdateFailed`.
3. **Test patchuje `voluptuous.Invalid` bo go nie zna** → dodaj `voluptuous` do `requirements-dev.txt` (już jest), użyj prawdziwego.
4. **Test mockuje `dt_util.utcnow = lambda: "2024-01-01"` (string zamiast datetime)** → użyj `freezegun` lub HA `dt_util.utcnow()` patch.
5. **Test podstawia coordinator jako SimpleNamespace** → użyj `MagicMock(spec=ThesslaGreenModbusCoordinator)`.

**Jeżeli testy prowadzą do mocka który nie ma jakiegoś atrybutu HA:**
- Błąd nie leży w produkcji (bo `getattr(x, attr, None)` maskował go).
- Błąd leży w teście który użył niepełnego stuba.

**Progres:** jeśli po wszystkich fixach `pytest -x -q` pokazuje że padło np. 30 testów, to znaczy że 30 testów opierało się na jakimś z 10 smelli. Naprawienie testów jest drugim krokiem.

---

## Metryki docelowe

```
                          v2.3.9         v2.4.0 (target)
Linie produkcji:         ~14500         ~13700-14000
Test-compat code:          ~400           ~0
sys.modules hacks:            4              0 (minus scanner_core.py shim, który zostaje bo różni się)
getattr z default w krytycznych ścieżkach:  ~30    ~10
# pragma: no cover w config_flow:   67    ~15
Klasy/funkcje istniejące tylko dla testów:  ~8    0
Test suite pass rate:     ~100%          po napraw testów: 100%
```

---

## Bump wersji i CHANGELOG

**Plik:** `custom_components/thessla_green_modbus/manifest.json`
```json
"version": "2.4.0",
```

**Plik:** `pyproject.toml`
```toml
version = "2.4.0"
```

**Plik:** `CHANGELOG.md`:
```markdown
## 2.4.0 — Production code detox

This release focuses on removing accumulated test-compat hacks from production code.
No user-facing changes; integration behavior is unchanged. Tests have been rewritten
to use `pytest-homeassistant-custom-component` properly.

### Removed
- `_update_failed_exception` in coordinator — no longer scans `sys.modules` for test modules to build compatibility `UpdateFailed` subclasses. Direct `UpdateFailed` is used everywhere.
- `__init__.py` alias for `custom_components.thessla_green_modbus.__init__.er` registered in `sys.modules`. Tests now use standard `monkeypatch.setattr` paths.
- `entity_mappings.py` shim. All imports updated to `from .mappings import X`.
- `_async_patch_coordinator_compat` and `_PermissiveCapabilities` fallback class. Coordinator now requires fully-initialized instance; tests use `MagicMock(spec=ThesslaGreenModbusCoordinator)` where needed.
- `_SafeDTUtil` wrapper class. Direct `homeassistant.util.dt` is re-exported.
- `super().__init__()` TypeError fallback in `ThesslaGreenModbusCoordinator.__init__`.
- `_FallbackFlowBase` in `config_flow.py` — unused class that pretended to be ConfigFlow for test envs.
- `_VolInvalid` + `vol.Invalid = VOL_INVALID` monkey-patch of voluptuous at import time.
- 7-level fallback in `_required` helper; direct `vol.Required` is used.
- `getattr(self.entry, "async_start_reauth", None)` defensive access — HA guarantees the method exists.
- Config entry migration for `version == 1`. Installations must be on `version >= 2` (users upgrading from pre-2021 installations need to reconfigure).

### Changed
- `except BaseException` with `exc.__class__.__name__ == "UpdateFailed"` string comparison in `__init__.py` replaced with clean `except Exception` + `isinstance(exc, UpdateFailed)`.
- Config-flow schema/required wrappers consolidated to simple delegates over `voluptuous`.

### Fixed
- Several production code paths that could mask real bugs when test mocks were incomplete — these paths returned True/empty/silent-ok instead of raising. Now any AttributeError from coordinator usage is surfaced instead of being swallowed by defensive `getattr`.

### Migration notes for test writers
- Do not define `class UpdateFailed(Exception)` in tests. Use `from homeassistant.helpers.update_coordinator import UpdateFailed`.
- Do not use `SimpleNamespace` as a coordinator stub. Use `MagicMock(spec=ThesslaGreenModbusCoordinator)` or `pytest-homeassistant-custom-component` fixtures.
- Do not patch `dt_util.utcnow = lambda: "some-string"`. Use `freezegun` or patch to a real datetime.
- Do not patch `voluptuous.Invalid` or `voluptuous.Required`. These are stable APIs.
```

---

## Notatki końcowe

**Dlaczego to jest major (2.4.0):**
- Formalnie: test API się zmienia, niektóre wewnętrzne symbole znikają.
- Realnie: integracja z punktu widzenia użytkownika zachowuje się identycznie.
- HACS / HA nie widzą różnicy. Instalacje nie wymagają rekonfiguracji (poza wyjątkowym przypadkiem entry.version == 1, jeśli zdecydowano się usunąć tę ścieżkę).

**Ryzyko regresu — średnie.** Nie niskie:
- Fix #1, #4 — usuwają kod obsługi edge-case'ów, które *mogły* się zdarzać w produkcji (np. testowa klasa UpdateFailed niesubkluje się nigdzie w runtime, ale `_PermissiveCapabilities` mogło podtrzymywać kod który wywoływał capability na coordynatorze przed pełną inicjalizacją).
- Fix #7 — dotyka najbardziej złożony plik (`config_flow.py`, 1368 linii). Testy config_flow-a są kluczowe. Po refactorze upewnij się że `test_config_flow.py` (73 KB) przechodzi w 100%.

**Testy padające po fixach:** oczekiwane i pożądane. Każdy padający test to dokumentacja problemu. Nie cofać zmian w produkcji — naprawiać testy.

**Pomijamy w tym release:**
- Pełny refactor dataclass `CoordinatorConfig`. Po odtruciu production code łatwiej zaprojektować poprawne API.
- Dalszy split `scanner/core.py`.
- `__init__.py` split (1128 linii).

Te zostają do v2.5.0.

**Gdy fix staje się niemożliwy:** jeżeli któryś test polega na `_PermissiveCapabilities` i jego przepisanie wymaga znajomości domeny której nie ma, **zostaw komentarz `# TODO(v2.4.0 detox):`** i jedź dalej. Kosmetyczny dług jest lepszy niż martwy kod w produkcji.
