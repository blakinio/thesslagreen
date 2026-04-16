# thessla_green_modbus — instrukcja napraw dla Claude Code (v3)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main`
**Wersja docelowa:** `2.3.1 → 2.3.2`
**Data audytu:** 2026-04-16

---

## Stan wyjściowy po v2.3.1

**Co już działa (nie ruszać):**
- ✅ Ruff (custom_components + tests + tools) — clean, 0 findings z aktualnym rulesetem (F,E,W,B,SIM,RUF,UP,I,PERF,BLE).
- ✅ Fixes #0–#8 z audytu v2 wdrożone (widoczne w `CHANGELOG.md` → sekcja 2.3.1).
- ✅ Tłumaczenia: parytet kluczy w `strings.json` / `en.json` / `pl.json`.

**Co tym audytem bierzemy na tapetę — mypy strict:**
- ❌ **343 błędy** mypy w trybie `strict` (`disallow_untyped_defs = true`, `warn_unused_ignores = true`).
- Rozkład na kategorie:

```
148  attr-defined       ← mixiny coordinator/scanner odwołują się do atrybutów rodzica
 45  no-untyped-def     ← głównie stuby fallback-import
 33  unused-ignore      ← pozostałości po czyszczeniu shimów py<3.13 (Fix #6 v2)
 31  union-attr         ← modbus_transport — wywołania na self.client bez None-guard
 17  misc               ← "conditional function variants must have identical signatures"
 15  no-any-return
 10  assignment
  8  has-type           ← _last_power_timestamp, _total_energy bez annotation
  8  arg-type
  8  valid-type         ← climate.py, ClimateEntity=getattr(...) antywzorzec
  6  operator           ← None >> int w _coordinator_capabilities BCD decode
  5  redundant-cast
  3  no-redef
  2  override
  2  index
```

- Rozkład na pliki (top 13):

```
 65  _coordinator_schedule.py
 64  _coordinator_io.py
 34  climate.py
 25  config_flow.py
 22  scanner_core.py
 17  __init__.py
 11  _scanner_transport_mixin.py
 10  scanner_register_maps.py
 10  _coordinator_capabilities.py
  9  _scanner_registers_mixin.py
  9  scanner_device_info.py
  8  modbus_transport.py
  8  const.py
```

**Dlaczego to ma znaczenie:** `mypy` w `pyproject.toml` jest skonfigurowany z `disallow_untyped_defs = true`, `warn_unused_ignores = true`. Integracja się uruchamia (runtime jest OK), ale CI typing-check padnie. Każdy z tych 343 błędów to albo: (a) prawdziwy potencjalny `AttributeError` / `TypeError` w runtime gdy warunki brzegowe zagrają, albo (b) kłamstwo w typach, które utrudnia refactor. Po naprawie #1–#4 spada ~280 błędów (80%) w 4 commitach.

**Zalecana kolejność wdrożenia:**
1. **Fix #1 — `climate.py` getattr antywzorzec** (34 err, 1 plik, największy ROI per zmiana)
2. **Fix #2 — mixiny coordinator/scanner (atrybuty + stub-metody)** (~160 err, 6 plików)
3. **Fix #3 — `modbus_transport.py` None-guards** (8 err, 1 plik)
4. **Fix #4 — identyczne sygnatury w conditional shimach** (~25 err, 4 pliki)
5. **Fix #5 — `_coordinator_capabilities.py` BCD None-guard** (6 err)
6. **Fix #6 — cleanup `unused-ignore`** (33 err, kosmetyka)
7. **Fix #7 — pozostałe: `scanner_helpers.py`, `registers/loader.py`, `modbus_helpers.py`, `scanner_device_info.py`**

Po każdym Fixie uruchomić:
```bash
mypy custom_components/thessla_green_modbus/
ruff check custom_components/thessla_green_modbus/ tests/ tools/
pytest -x  # szybki smoke
```

---

## Fix #1 — `climate.py`: wycięcie `getattr(ha_components, ...)` antywzorca

**Plik:** `custom_components/thessla_green_modbus/climate.py`

**Dowód problemu:**
Plik rozpoczyna się od:
```python
climate_component = getattr(ha_components, "climate", None)
ClimateEntity = getattr(climate_component, "ClimateEntity", object)
HVACMode = getattr(
    climate_component,
    "HVACMode",
    type("HVACMode", (), {"OFF": "off", "AUTO": "auto", "FAN_ONLY": "fan_only"}),
)
```

Skutek: mypy widzi `ClimateEntity: Any | type`, `HVACMode: Any | type` itd. Każde użycie (`HVACMode.AUTO`, `HVACMode.OFF`, dziedziczenie `class ThesslaGreenClimate(ClimateEntity)`) produkuje `valid-type` / `union-attr`. To relikt ery HA <2024 — manifest wymaga `homeassistant: 2026.1.0`, więc symbole są dostępne na pewno. Fallback „runtime type" to martwy kod: przy braku `homeassistant.components.climate` integracja i tak nie wystartuje (HA nie wczyta jej).

**Dodatkowy kontekst:** fallback dotyczy tylko trybu testowego (pytest bez HA). Ale nawet tam `pytest-homeassistant-custom-component` dostarcza HA. Jedyna realna droga wykonania fallbacku — uruchomienie `tools/py_compile_all.py` bez HA w venv — nie wymaga funkcjonalnego `ClimateEntity`, tylko kompilacji.

### Krok 1a — zastąp blok getattr normalnym importem

**Plik:** `custom_components/thessla_green_modbus/climate.py`

#### SZUKAJ (linie 1-36)
```python
"""Climate entity for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import homeassistant.components as ha_components
from homeassistant import const as ha_const
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

climate_component = getattr(ha_components, "climate", None)
ClimateEntity = getattr(climate_component, "ClimateEntity", object)
ClimateEntityFeature = getattr(climate_component, "ClimateEntityFeature", int)
HVACAction = getattr(
    climate_component,
    "HVACAction",
    type(
        "HVACAction",
        (),
        {"OFF": "off", "FAN": "fan", "HEATING": "heating", "COOLING": "cooling", "IDLE": "idle"},
    ),
)
HVACMode = getattr(
    climate_component,
    "HVACMode",
    type("HVACMode", (), {"OFF": "off", "AUTO": "auto", "FAN_ONLY": "fan_only"}),
)

ATTR_TEMPERATURE = getattr(ha_const, "ATTR_TEMPERATURE", "temperature")
UnitOfTemperature = getattr(
    ha_const, "UnitOfTemperature", type("UnitOfTemperature", (), {"CELSIUS": "°C"})
)
```

#### ZASTĄP
```python
"""Climate entity for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
```

### Krok 1b — usuń `# noqa: E402` z późniejszych importów

#### SZUKAJ
```python
from .const import (  # noqa: E402
    SPECIAL_FUNCTION_MAP,
    TEMPERATURE_MAX_C,
    TEMPERATURE_MIN_C,
    TEMPERATURE_STEP_C,
    holding_registers,
)
from .coordinator import ThesslaGreenModbusCoordinator  # noqa: E402
from .entity import ThesslaGreenEntity  # noqa: E402
```

#### ZASTĄP
```python
from .const import (
    SPECIAL_FUNCTION_MAP,
    TEMPERATURE_MAX_C,
    TEMPERATURE_MIN_C,
    TEMPERATURE_STEP_C,
    holding_registers,
)
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
```

(po Kroku 1a nie ma już kodu niestandardowo zainicjalizowanego przed tymi importami, więc `E402` nie jest już wywoływane).

### Krok 1c — zastąp `getattr(ClimateEntityFeature, ...)` stałymi

#### SZUKAJ
```python
_FEATURE_TARGET_TEMPERATURE = getattr(ClimateEntityFeature, "TARGET_TEMPERATURE", 1)
_FEATURE_FAN_MODE = getattr(ClimateEntityFeature, "FAN_MODE", 2)
_FEATURE_PRESET_MODE = getattr(ClimateEntityFeature, "PRESET_MODE", 4)
_FEATURE_TURN_ON = getattr(ClimateEntityFeature, "TURN_ON", 0)
_FEATURE_TURN_OFF = getattr(ClimateEntityFeature, "TURN_OFF", 0)
```

#### ZASTĄP
```python
# ClimateEntityFeature.TURN_ON / TURN_OFF dodane w HA 2024.2; wymagane przez manifest (2026.1.0).
_FEATURE_TARGET_TEMPERATURE = ClimateEntityFeature.TARGET_TEMPERATURE
_FEATURE_FAN_MODE = ClimateEntityFeature.FAN_MODE
_FEATURE_PRESET_MODE = ClimateEntityFeature.PRESET_MODE
_FEATURE_TURN_ON = ClimateEntityFeature.TURN_ON
_FEATURE_TURN_OFF = ClimateEntityFeature.TURN_OFF
```

### Krok 1d — dodaj test smoke

**Plik:** `tests/test_climate.py` (dodaj na końcu, nie zastępuj istniejącego)

```python
def test_climate_imports_real_ha_symbols() -> None:
    """Guard against regression: climate.py must use real HA imports, not getattr fallback.

    The getattr pattern caused 34 mypy errors. This test ensures we don't revert
    to runtime-resolved symbols that mypy can't type-check.
    """
    from custom_components.thessla_green_modbus import climate

    # Must be real enum/class, not getattr fallback
    assert hasattr(climate.HVACMode, "AUTO")
    assert hasattr(climate.HVACMode, "OFF")
    assert hasattr(climate.HVACAction, "HEATING")
    assert climate.ClimateEntity.__module__.startswith("homeassistant.")
```

### Oczekiwany efekt
- `mypy custom_components/thessla_green_modbus/climate.py` → z 34 błędów do ≤2 (resztki z coordinator references).
- `ruff` bez zmian (był czysty).
- `pytest tests/test_climate.py` → pass.

---

## Fix #2 — Mixiny coordinator/scanner: atrybuty i stub-metody

**Pliki dotknięte:**
- `custom_components/thessla_green_modbus/_coordinator_io.py` (64 err)
- `custom_components/thessla_green_modbus/_coordinator_schedule.py` (65 err)
- `custom_components/thessla_green_modbus/_coordinator_capabilities.py` (~10 err)
- `custom_components/thessla_green_modbus/_scanner_registers_mixin.py` (9 err)
- `custom_components/thessla_green_modbus/_scanner_transport_mixin.py` (11 err)
- `custom_components/thessla_green_modbus/_scanner_capabilities_mixin.py` (few err)

**Dowód problemu:**
`_coordinator_io.py:24` definiuje:
```python
class _ModbusIOMixin:
    """Read-path Modbus methods used by the coordinator."""

    _transport: BaseModbusTransport | None
    client: Any | None
    statistics: dict[str, Any]
    available_registers: dict[str, set[str]]
    _register_groups: dict[str, list[tuple[int, int]]]
    effective_batch: int
    _failed_registers: set[str]
```

…ale potem używa `self.slave_id`, `self.retry`, `self.timeout`, `self.backoff`, `self.backoff_jitter`, `self._ensure_connection`, `self._find_register_name`, `self._process_register_value`, `self._clear_register_failure`, `self._mark_registers_failed` — 20+ atrybutów bez deklaracji. Wszystkie istnieją w `ThesslaGreenModbusCoordinator` (`coordinator.py`), ale mixin nie ma żadnej „wiedzy" o rodzicu.

To samo w `_coordinator_schedule.py` — używa `self._call_modbus`, `self._get_client_method`, `self._write_lock`, `self._disconnect`.

**Rozwiązanie — dwa podejścia:**
- **Podejście A:** Zdefiniuj `Protocol` z wszystkimi oczekiwanymi atrybutami/metodami w nowym pliku `_coordinator_protocol.py`. Każdy mixin importuje go w `TYPE_CHECKING`. Wada: duplikacja sygnatur między mixinami a Protocolem.
- **Podejście B (preferowane):** Dodaj brakujące adnotacje atrybutów wprost do każdej klasy mixin. Metody referencjonowane między mixinami (np. `_call_modbus` w schedule → `_ModbusIOMixin._call_modbus`) oznacz jako abstrakcyjne sygnatury `def _call_modbus(self, ...) -> Any: ...`.

**Wybieramy podejście B** — mniej plumbingu, jeden commit per mixin, czytelność „kontraktu rodzica" bezpośrednio w pliku mixinu.

### Krok 2a — `_coordinator_io.py`: dodaj brakujące adnotacje

**Plik:** `custom_components/thessla_green_modbus/_coordinator_io.py`

#### SZUKAJ (linie 24-34)
```python
class _ModbusIOMixin:
    """Read-path Modbus methods used by the coordinator."""

    _transport: BaseModbusTransport | None
    client: Any | None
    statistics: dict[str, Any]
    available_registers: dict[str, set[str]]
    _register_groups: dict[str, list[tuple[int, int]]]
    effective_batch: int
    _failed_registers: set[str]
```

#### ZASTĄP
```python
class _ModbusIOMixin:
    """Read-path Modbus methods used by the coordinator.

    This mixin is composed into :class:`ThesslaGreenModbusCoordinator` which
    provides all attributes declared below. Declarations exist only so mypy
    can type-check the mixin in isolation; the real values are set by the
    coordinator's ``__init__``.
    """

    # Transport / connection (set by ThesslaGreenModbusCoordinator.__init__)
    _transport: BaseModbusTransport | None
    client: Any | None
    slave_id: int
    timeout: float
    retry: int
    backoff: float
    backoff_jitter: float

    # Runtime state
    statistics: dict[str, Any]
    available_registers: dict[str, set[str]]
    _register_groups: dict[str, list[tuple[int, int]]]
    effective_batch: int
    _failed_registers: set[str]

    # Methods provided by other mixins or the coordinator proper. Declaring
    # them here lets mypy resolve ``self._ensure_connection(...)`` etc. from
    # within this mixin without forcing a circular import on the coordinator.
    async def _ensure_connection(self) -> bool: ...
    def _find_register_name(
        self, address: int, register_type: str
    ) -> str | None: ...
    def _process_register_value(
        self, register_name: str, raw_value: int
    ) -> Any: ...
    def _clear_register_failure(self, register_name: str) -> None: ...
    def _mark_registers_failed(
        self, register_names: list[str] | set[str]
    ) -> None: ...
```

**Uwaga — `...` vs `pass`:** PEP 484 explicite dopuszcza `...` jako ciało stub-metody. Mypy traktuje to jako abstract shape. Metody *nie będą* wołane na instancji `_ModbusIOMixin` samej w sobie — zawsze są resolwowane przez MRO z `ThesslaGreenModbusCoordinator`. **Ważne:** w `coordinator.py` prawdziwe metody `_find_register_name`, `_process_register_value`, `_clear_register_failure`, `_mark_registers_failed` nadpiszą te stuby. Upewnij się, że sygnatury stubów są identyczne z rzeczywistymi — inaczej mypy zgłosi `override`.

**Weryfikacja sygnatur stubów:**
```bash
grep -n "def _ensure_connection\|def _find_register_name\|def _process_register_value\|def _clear_register_failure\|def _mark_registers_failed" custom_components/thessla_green_modbus/coordinator.py
```

Porównaj wypisane sygnatury ze stubami wyżej i dostosuj typy argumentów, jeśli różnią się.

### Krok 2b — `_coordinator_schedule.py`: dodaj brakujące adnotacje

**Plik:** `custom_components/thessla_green_modbus/_coordinator_schedule.py`

Znajdź otwarcie klasy `_CoordinatorScheduleMixin` (linia 24). Wstaw deklaracje atrybutów tuż po docstringu klasy, przed pierwszą metodą.

**Najpierw upewnij się, że masz właściwe importy na górze pliku:**

```bash
head -20 custom_components/thessla_green_modbus/_coordinator_schedule.py
```

Jeśli brakuje `asyncio` lub `TYPE_CHECKING`, dodaj:

```python
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .modbus_transport import BaseModbusTransport
```

Następnie, **tuż po `class _CoordinatorScheduleMixin:`** i jego docstringu, **wstaw**:

```python
    # Attributes provided by ThesslaGreenModbusCoordinator / other mixins.
    # Declared for mypy; real values come from the coordinator's __init__.
    _transport: "BaseModbusTransport | None"
    client: Any | None
    slave_id: int
    retry: int
    effective_batch: int
    _write_lock: asyncio.Lock

    async def _call_modbus(
        self, func: Any, *args: Any, attempt: int = 1, **kwargs: Any
    ) -> Any: ...
    def _get_client_method(self, name: str) -> Any: ...
    async def _ensure_connection(self) -> bool: ...
    async def _disconnect(self) -> None: ...
    def _clear_register_failure(self, register_name: str) -> None: ...
```

Sprawdź potem sygnatury `_call_modbus` i `_get_client_method` w `_coordinator_io.py` (Krok 2a) oraz `coordinator.py`, żeby stuby tutaj się zgadzały 1:1.

### Krok 2c — `_coordinator_capabilities.py`: dodaj `device_info`, `_last_power_timestamp`, `_total_energy`

**Plik:** `custom_components/thessla_green_modbus/_coordinator_capabilities.py`

#### SZUKAJ (linia 18-31 — początek klasy)
```python
class _CoordinatorCapabilitiesMixin:
    """Capability and derived-value logic for the coordinator."""

    _STANDBY_POWER_W: float = 10.0
    _MODEL_POWER_DATA: ClassVar[Mapping[int, tuple[float, float]]] = MappingProxyType(
        {
            300: (105.0, 1150.0),
            400: (170.0, 1500.0),
            420: (94.0, 1449.0),
            500: (255.0, 1850.0),
            550: (345.0, 1950.0),
        }
    )
    _MODEL_FLOW_TOLERANCE = 15
```

#### ZASTĄP
```python
class _CoordinatorCapabilitiesMixin:
    """Capability and derived-value logic for the coordinator."""

    # Attributes populated by ThesslaGreenModbusCoordinator.__init__
    device_info: dict[str, Any]
    _last_power_timestamp: datetime | None
    _total_energy: float

    _STANDBY_POWER_W: float = 10.0
    _MODEL_POWER_DATA: ClassVar[Mapping[int, tuple[float, float]]] = MappingProxyType(
        {
            300: (105.0, 1150.0),
            400: (170.0, 1500.0),
            420: (94.0, 1449.0),
            500: (255.0, 1850.0),
            550: (345.0, 1950.0),
        }
    )
    _MODEL_FLOW_TOLERANCE = 15
```

### Krok 2d — scanner mixins

Powtórz wzorzec dla:
- `_scanner_registers_mixin.py` — znajdź `class _ScannerRegistersMixin:` i dodaj brakujące atrybuty (`self.host`, `self.port`, `self.slave_id`, `self._transport`, `self.client`) oraz stub-metody z `scanner_core.py`, które mixin wywołuje.
- `_scanner_transport_mixin.py` — to samo dla `class _ScannerTransportMixin:`.
- `_scanner_capabilities_mixin.py` — dla `class _ScannerCapabilitiesMixin:`.

**Procedura:**
1. Uruchom `mypy custom_components/thessla_green_modbus/_scanner_<nazwa>_mixin.py 2>&1 | grep attr-defined`.
2. Każdą linijkę typu `"_ScannerXMixin" has no attribute "foo"  [attr-defined]` rozwiązuj dodając `foo: <typ>` lub stub-metodę na górze klasy.
3. Dla typu `<typ>` — sprawdź w `scanner_core.py` jak atrybut jest zainicjalizowany w `__init__` klasy `ThesslaGreenDeviceScanner`:
   ```bash
   grep -n "self\." custom_components/thessla_green_modbus/scanner_core.py | grep "= " | head -40
   ```

### Oczekiwany efekt
- `attr-defined` spada ze 148 → ~5-10 (resztki edge-cases).
- `has-type` (8 błędów) → 0 po Kroku 2c.
- Runtime bez zmian — `...` w ciele metod stubów jest ignorowane przez MRO.

---

## Fix #3 — `modbus_transport.py`: None-guards po `ensure_connected`

**Plik:** `custom_components/thessla_green_modbus/modbus_transport.py`

**Dowód problemu:**
Wzorzec powtarzający się 8× w pliku (2 klasy × 4 metody):
```python
async def read_input_registers(
    self, slave_id: int, address: int, *, count: int, attempt: int = 1,
) -> Any:
    if self.client is None:
        await self.ensure_connected()
    return await self.call(
        self.client.read_input_registers,  # ← mypy: "Item None has no attribute..."
        slave_id, address, count=count, attempt=attempt,
    )
```

Problem: `self.client: AsyncModbusTcpClient | None = None` (linia 304/495). Po `await self.ensure_connected()` mypy nie wie, że `self.client` nie jest już `None` — bo `ensure_connected` w `BaseModbusTransport` nie zwraca informacji o stanie, tylko rzuca wyjątek przy porażce.

**Rozwiązanie:** wymuś narrowing przez `assert`. W runtime jest to no-op przy `python -O` (assertions są wycinane). Alternatywnie `ensure_connected` mogłoby zwracać klienta, ale to szersza zmiana — trzymamy się `assert`.

### Krok 3a — dodaj `assert` po każdym `ensure_connected`

Zastosuj do **wszystkich 8 metod** w `modbus_transport.py`. Lista linii (z bieżącego stanu repo):

| Linia | Metoda                    | Klasa                |
|-------|---------------------------|----------------------|
| 395   | `read_input_registers`    | `TcpModbusTransport` |
| 413   | `read_holding_registers`  | `TcpModbusTransport` |
| 431   | `write_register`          | `TcpModbusTransport` |
| 449   | `write_registers`         | `TcpModbusTransport` |
| 538   | `read_input_registers`    | `RtuModbusTransport` |
| 556   | `read_holding_registers`  | `RtuModbusTransport` |
| 574   | `write_register`          | `RtuModbusTransport` |
| 592   | `write_registers`         | `RtuModbusTransport` |

**Dla każdej z 8 metod:**

#### SZUKAJ (wzorzec powtarza się 8×)
```python
    if self.client is None:
        await self.ensure_connected()
    return await self.call(
        self.client.<METHOD>,
```

#### ZASTĄP (`<METHOD>` zostaje — to placeholder)
```python
    if self.client is None:
        await self.ensure_connected()
    assert self.client is not None, "ensure_connected must populate self.client"
    return await self.call(
        self.client.<METHOD>,
```

**Uwaga:** nie używaj globalnego find-and-replace — klucze kontekstu (`<METHOD>`) różnią się. Idź po jednej metodzie na raz:

```bash
# Pokaż wszystkie miejsca do poprawy:
grep -n "self\.client\.\(read\|write\)" custom_components/thessla_green_modbus/modbus_transport.py
```

### Krok 3b (opcjonalny, nie w tym PR-ze) — alternatywa

**Lepsze długoterminowo, ale szersza zmiana.** Zmień kontrakt `ensure_connected` tak, by zwracał klienta:

```python
    async def ensure_connected(self) -> Any:
        """Ensure client is connected, returning the live client instance."""
        # ... existing connection logic ...
        assert self.client is not None
        return self.client
```

Wtedy każda metoda I/O robi:
```python
    client = self.client if self.client is not None else await self.ensure_connected()
    return await self.call(client.read_input_registers, ...)
```

**Rekomendacja:** Krok 3a (assert) w tym fixie, Krok 3b odłóż na osobny refactor — zmiana kontraktu `ensure_connected` dotyka też scannera i wymaga przejrzenia wszystkich callsite'ów.

### Oczekiwany efekt
- `union-attr` errors w `modbus_transport.py` spada z 8 → 0.
- **Uwaga:** było 31 `union-attr` total; pozostałe 23 to z innych plików (np. `climate.py` — rozwiązane przez Fix #1, `mappings/legacy.py:127/147` — rozwiązane przez Fix #6, scanner — przez Fix #2d).

---

## Fix #4 — Conditional shim signatures

**Pliki:**
- `custom_components/thessla_green_modbus/scanner_register_maps.py` (5 shimów)
- `custom_components/thessla_green_modbus/const.py` (1 shim)
- `custom_components/thessla_green_modbus/mappings/_helpers.py` (1 shim)
- `custom_components/thessla_green_modbus/mappings/_loaders.py` (1 shim)

**Dowód problemu:**
`scanner_register_maps.py:18`:
```python
try:
    from .registers.loader import (
        async_get_all_registers,       # def async_get_all_registers(hass, json_path=None) -> Coroutine[..., list[RegisterDef]]
        async_registers_sha256,        # def async_registers_sha256(hass, json_path) -> Coroutine[..., str]
        get_all_registers,             # def get_all_registers(json_path=None) -> list[RegisterDef]
        get_registers_path,            # def get_registers_path() -> Path
        registers_sha256,              # def registers_sha256(json_path) -> str
    )
except (ImportError, AttributeError):
    async def async_get_all_registers(*_args, **_kwargs):        # ← brak adnotacji
        return []
    async def async_registers_sha256(*_args, **_kwargs) -> str:  # ← sygnatura ≠ oryginał
        return ""
    def get_all_registers(*_args, **_kwargs):                    # ← brak adnotacji
        return []
```

Mypy zgłasza:
```
error: All conditional function variants must have identical signatures  [misc]
error: Function is missing a type annotation  [no-untyped-def]
```

**Rozwiązanie:** stuby fallback muszą mieć **identyczną sygnaturę** z oryginalnymi importami. Nie pomoże `*_args, **_kwargs`.

**Najpierw — ustal prawdziwe sygnatury:**
```bash
grep -nE "^(async )?def (async_get_all_registers|async_registers_sha256|get_all_registers|get_registers_path|registers_sha256|get_registers_by_function)" custom_components/thessla_green_modbus/registers/loader.py
```

Wypisz sobie każdą sygnaturę 1:1 i użyj jako bazy dla fallbacków.

### Krok 4a — `scanner_register_maps.py`

#### SZUKAJ (linie 1-31)
```python
"""Register-definition caches and map builders for scanner usage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import (
        async_get_all_registers,
        async_registers_sha256,
        get_all_registers,
        get_registers_path,
        registers_sha256,
    )
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    async def async_get_all_registers(*_args, **_kwargs):
        return []

    async def async_registers_sha256(*_args, **_kwargs) -> str:
        return ""

    def get_all_registers(*_args, **_kwargs):
        return []

    def get_registers_path(*_args, **_kwargs) -> Path:
        return Path(".")

    def registers_sha256(*_args, **_kwargs) -> str:
        return ""
```

#### ZASTĄP
```python
"""Register-definition caches and map builders for scanner usage."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .registers.loader import RegisterDef

try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import (
        async_get_all_registers,
        async_registers_sha256,
        get_all_registers,
        get_registers_path,
        registers_sha256,
    )
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    async def async_get_all_registers(
        hass: Any | None = None, json_path: Path | str | None = None
    ) -> list["RegisterDef"]:
        return []

    async def async_registers_sha256(
        hass: Any | None, json_path: Path | str
    ) -> str:
        return ""

    def get_all_registers(
        json_path: Path | str | None = None,
    ) -> list["RegisterDef"]:
        return []

    def get_registers_path() -> Path:
        return Path(".")

    def registers_sha256(json_path: Path | str) -> str:
        return ""
```

**Uwaga:** sygnatury wyżej są zrekonstruowane z mypy-output. **Obowiązkowo zweryfikuj** z `registers/loader.py` przed commitem:

```bash
# Porównaj każdą sygnaturę:
sed -n '/^async def async_get_all_registers/,/^    """/p' custom_components/thessla_green_modbus/registers/loader.py
sed -n '/^async def async_registers_sha256/,/^    """/p' custom_components/thessla_green_modbus/registers/loader.py
sed -n '/^def get_all_registers/,/^    """/p' custom_components/thessla_green_modbus/registers/loader.py
sed -n '/^def get_registers_path/,/^    """/p' custom_components/thessla_green_modbus/registers/loader.py
sed -n '/^def registers_sha256/,/^    """/p' custom_components/thessla_green_modbus/registers/loader.py
```

Jeśli oryginał różni się (np. `json_path` nie ma default, `hass` jest pozycyjny bez default), **dopasuj fallback 1:1**.

### Krok 4b — `const.py`

#### SZUKAJ (linie 13-18)
```python
try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import get_registers_by_function
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    def get_registers_by_function(fn: str):
        return []
```

#### ZASTĄP
```python
try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import get_registers_by_function
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    def get_registers_by_function(
        fn: str, json_path: Path | str | None = None
    ) -> list[Any]:
        return []
```

(Oryginał bierze `fn: str, json_path: Path | str | None = None` — zweryfikuj w `registers/loader.py`.)

### Krok 4c — `mappings/_helpers.py`

#### SZUKAJ (linie 14-19)
```python
try:  # pragma: no cover - optional during isolated tests
    from ..registers.loader import get_all_registers
except (ImportError, AttributeError):  # pragma: no cover

    def get_all_registers(*_args, **_kwargs):
        return []
```

#### ZASTĄP
```python
try:  # pragma: no cover - optional during isolated tests
    from ..registers.loader import get_all_registers
except (ImportError, AttributeError):  # pragma: no cover

    def get_all_registers(
        json_path: "Path | str | None" = None,
    ) -> list[Any]:
        return []
```

### Krok 4d — `mappings/_loaders.py`

Otwórz plik, znajdź shim fallback przy linii ~29 (`mypy` raportuje `Function is missing a type annotation`):

```bash
sed -n '1,40p' custom_components/thessla_green_modbus/mappings/_loaders.py
```

Zidentyfikuj shim analogiczny do tych z 4a-4c i napraw tym samym wzorcem — zidentyfikuj prawdziwą sygnaturę w `registers/loader.py`, sklonuj ją do fallbacku.

### Oczekiwany efekt
- 17× `misc "conditional function variants must have identical signatures"` → 0.
- `no-untyped-def` związane z shimami → 0 (~10 błędów).

---

## Fix #5 — `_coordinator_capabilities.py`: None-guard na BCD decode

**Plik:** `custom_components/thessla_green_modbus/_coordinator_capabilities.py`

**Dowód problemu (linie 220-241):**
```python
try:
    raw_yymm = data.get("date_time")
    raw_ddtt = data.get("date_time_ddtt")
    raw_ggmm = data.get("date_time_ggmm")
    raw_sscc = data.get("date_time_sscc")
    if all(v is not None for v in (raw_yymm, raw_ddtt, raw_ggmm, raw_sscc)):

        def _bcd(b: int) -> int:
            return ((b >> 4) & 0xF) * 10 + (b & 0xF)

        yy = _bcd((raw_yymm >> 8) & 0xFF)   # ← mypy: Unsupported operand for >> (None and int)
        mm = _bcd(raw_yymm & 0xFF)           # ← mypy: same
        dd = _bcd((raw_ddtt >> 8) & 0xFF)
        hh = _bcd((raw_ggmm >> 8) & 0xFF)
        mi = _bcd(raw_ggmm & 0xFF)
        ss = _bcd((raw_sscc >> 8) & 0xFF)
```

Problem: `all(v is not None for v in (...))` z generatorem nie zwęża typów dla mypy (generator expression nie propaguje narrowing-info na zmienne nazwane poza nim). Mypy wciąż widzi `raw_yymm: Any | None`.

**Rozwiązanie:** explicite `is not None` na każdej zmiennej w `if`.

### Krok 5 — przepisz blok BCD decode

#### SZUKAJ (linie ~220-243)
```python
        # Decode device clock from BCD registers 0-3
        try:
            raw_yymm = data.get("date_time")
            raw_ddtt = data.get("date_time_ddtt")
            raw_ggmm = data.get("date_time_ggmm")
            raw_sscc = data.get("date_time_sscc")
            if all(v is not None for v in (raw_yymm, raw_ddtt, raw_ggmm, raw_sscc)):

                def _bcd(b: int) -> int:
                    return ((b >> 4) & 0xF) * 10 + (b & 0xF)

                yy = _bcd((raw_yymm >> 8) & 0xFF)
                mm = _bcd(raw_yymm & 0xFF)
                dd = _bcd((raw_ddtt >> 8) & 0xFF)
                hh = _bcd((raw_ggmm >> 8) & 0xFF)
                mi = _bcd(raw_ggmm & 0xFF)
                ss = _bcd((raw_sscc >> 8) & 0xFF)
                year = 2000 + yy
                if 1 <= mm <= 12 and 1 <= dd <= 31 and hh <= 23 and mi <= 59 and ss <= 59:
                    data["device_clock"] = (
                        f"{year:04d}-{mm:02d}-{dd:02d}T{hh:02d}:{mi:02d}:{ss:02d}"
                    )
        except (TypeError, ValueError, AttributeError) as exc:  # pragma: no cover
            _LOGGER.debug("Failed to decode device clock: %s", exc)
```

#### ZASTĄP
```python
        # Decode device clock from BCD registers 0-3
        try:
            raw_yymm = data.get("date_time")
            raw_ddtt = data.get("date_time_ddtt")
            raw_ggmm = data.get("date_time_ggmm")
            raw_sscc = data.get("date_time_sscc")
            if (
                raw_yymm is not None
                and raw_ddtt is not None
                and raw_ggmm is not None
                and raw_sscc is not None
            ):

                def _bcd(b: int) -> int:
                    return ((b >> 4) & 0xF) * 10 + (b & 0xF)

                yy = _bcd((raw_yymm >> 8) & 0xFF)
                mm = _bcd(raw_yymm & 0xFF)
                dd = _bcd((raw_ddtt >> 8) & 0xFF)
                hh = _bcd((raw_ggmm >> 8) & 0xFF)
                mi = _bcd(raw_ggmm & 0xFF)
                ss = _bcd((raw_sscc >> 8) & 0xFF)
                year = 2000 + yy
                if 1 <= mm <= 12 and 1 <= dd <= 31 and hh <= 23 and mi <= 59 and ss <= 59:
                    data["device_clock"] = (
                        f"{year:04d}-{mm:02d}-{dd:02d}T{hh:02d}:{mi:02d}:{ss:02d}"
                    )
        except (TypeError, ValueError, AttributeError) as exc:  # pragma: no cover
            _LOGGER.debug("Failed to decode device clock: %s", exc)
```

Rozwinięcie `all(... generator ...)` na explicite `and` chain zwęża typy — mypy teraz widzi, że wszystkie 4 zmienne w bloku `then` są `Any` *bez None* (czyli wystarczająco, by operacje `>>` i `&` nie wyrzucały errorów).

### Oczekiwany efekt
- 6× `operator` → 0 w tym bloku.

---

## Fix #6 — Cleanup `unused-ignore`

**Pliki:** wszystkie z komentarzami `# type: ignore[...]` które mypy raportuje jako `unused-ignore`.

**Lista wstępna (z mypy output):**
- `custom_components/thessla_green_modbus/_compat.py:70` — `class DeviceInfo:` bez `# type: ignore[no-redef]` (mypy widzi redef z pierwszej próby importu).
- `custom_components/thessla_green_modbus/mappings/legacy.py:127,147` — `# type: ignore[union-attr]` nie pasuje; błąd to teraz `attr-defined` po restrukturyzacji.
- `custom_components/thessla_green_modbus/mappings/_helpers.py:77` — `# type: ignore[union-attr]` nie pokrywa `attr-defined`.
- `custom_components/thessla_green_modbus/const.py:251` — `# type: ignore[assignment]` już nie potrzebny.

**Procedura (33 lokalizacji):**
```bash
mypy custom_components/thessla_green_modbus/ 2>&1 | grep 'unused-ignore' > /tmp/unused_ignores.txt
wc -l /tmp/unused_ignores.txt  # powinno być ~33
```

Dla każdej linii:
1. Otwórz plik w lokalizacji z raportu.
2. Znajdź komentarz `# type: ignore[...]`.
3. **Uwaga:** nie kasuj bezmyślnie — `warn_unused_ignores = true` mówi tylko, że przy *obecnym* stanie kodu ignore jest zbędny. Po Fixach #1-#5 niektóre z tych `# type: ignore` mogą znów być potrzebne (albo z innym kodem błędu).
4. **Procedura bezpieczna:** najpierw zastosuj Fixy #1-#5, dopiero na końcu Fix #6 (regenerujesz listę unused z mypy, jest krótsza).

### Krok 6a — typowy przypadek: `mappings/legacy.py:127,147`

#### SZUKAJ (linie 119-128)
```python
            _alias_warning_logged = True
            if _parent is not None:
                _parent._alias_warning_logged = True  # type: ignore[union-attr]
```

#### ZASTĄP
```python
            _alias_warning_logged = True
            if _parent is not None:
                _parent._alias_warning_logged = True  # type: ignore[attr-defined]
```

(kod błędu się zmienił: `union-attr` → `attr-defined`, bo `sys.modules.get(__package__)` zwraca `ModuleType | None`, mypy po guardach zwęża do `ModuleType`, a ten nie ma atrybutu `_alias_warning_logged` w stub-pliku `types-setuptools`).

Analogicznie w linii 147.

### Krok 6b — `_compat.py:70`

#### SZUKAJ
```python
try:
    from homeassistant.helpers.device_registry import DeviceInfo
except (ModuleNotFoundError, ImportError):

    class DeviceInfo:
        """Minimal fallback DeviceInfo for tests."""
```

#### ZASTĄP
```python
try:
    from homeassistant.helpers.device_registry import DeviceInfo
except (ModuleNotFoundError, ImportError):

    class DeviceInfo:  # type: ignore[no-redef]
        """Minimal fallback DeviceInfo for tests."""
```

Porównaj z klasą `EntityCategory` wyżej — ta ma już `# type: ignore[no-redef]` — ujednolicenie.

### Krok 6c — `mappings/_helpers.py:77`

#### SZUKAJ (linia 77)
```python
        if _parent is not None:
            _parent._REGISTER_INFO_CACHE = cache  # type: ignore[union-attr]
```

#### ZASTĄP
```python
        if _parent is not None:
            _parent._REGISTER_INFO_CACHE = cache  # type: ignore[attr-defined]
```

### Krok 6d — pozostałe `unused-ignore`

Dla wszystkich pozostałych (~30) linii z listy `/tmp/unused_ignores.txt`:
1. Sprawdź, czy kod błędu jeszcze istnieje po Fixach #1-#5 (`mypy custom_components/thessla_green_modbus/<plik>.py 2>&1 | grep "<linia>:"`).
2. Jeśli linia w ogóle nie ma już mypy-errora → **usuń `# type: ignore[...]`**.
3. Jeśli jest inny błąd → **zmień kod błędu w `# type: ignore[<nowy>]`**.

### Oczekiwany efekt
- 33× `unused-ignore` → 0.
- 3× `no-redef` → 0 (po Kroku 6b).

---

## Fix #7 — Pozostałe

### Krok 7a — `modbus_helpers.py:225` `no-any-return`

**Plik:** `custom_components/thessla_green_modbus/modbus_helpers.py`

```bash
sed -n '220,235p' custom_components/thessla_green_modbus/modbus_helpers.py
```

Prawdopodobnie funkcja deklaruje `-> float`, ale zwraca wartość z JSON-a bez castingu (`Any`). Rozwiązanie — explicite `float(value)`:

```python
    return float(value)  # was: return value
```

### Krok 7b — `scanner_helpers.py:46,58,61,62`

**Plik:** `custom_components/thessla_green_modbus/scanner_helpers.py`

```bash
sed -n '40,70p' custom_components/thessla_green_modbus/scanner_helpers.py
```

Błąd `Incompatible types in assignment (expression has type "str | None", variable has type "int | None")` oznacza, że zmienna pierwotnie zadeklarowana jako `int | None` jest potem nadpisywana stringiem albo dictem. Rozszerz typ zmiennej o prawdziwe warianty:

```python
# było:
value: int | None = ...

# powinno być (dopasuj do realnego zakresu):
value: int | str | dict[str, float | int] | None = ...
```

Błąd `Value of type "int" is not indexable` (linie 61, 62) to konsekwencja tego samego problemu — po `value[key]` mypy widzi `int`, którego nie da się indeksować. Po rozszerzeniu typu dodaj `isinstance(value, dict)` guard przed indeksowaniem.

### Krok 7c — `registers/loader.py:352,706`

**Plik:** `custom_components/thessla_green_modbus/registers/loader.py`

#### Linia 352
Błąd: `Argument 1 to "int" has incompatible type "Any | None"; expected "str | Buffer | SupportsInt | SupportsIndex | SupportsTrunc"`

Znajdź:
```bash
sed -n '345,360p' custom_components/thessla_green_modbus/registers/loader.py
```

Dodaj guard:
```python
# było:
parsed_int = int(value)

# powinno być:
if value is None:
    raise ValueError("Expected numeric value for register.min/max, got None")
parsed_int = int(value)
```

(Dokładny kontekst zależy od otaczającego kodu — może to być parsing `register["min"]`/`register["max"]` z JSON-a.)

#### Linia 706 — `redundant-cast`
```bash
sed -n '700,710p' custom_components/thessla_green_modbus/registers/loader.py
```

Znajdź `cast(list[tuple[int, int]], ...)` gdzie obiekt już ma ten typ. Usuń `cast(...)` wrapper.

### Krok 7d — `scanner_device_info.py` missing annotations

`mypy custom_components/thessla_green_modbus/scanner_device_info.py` pokazuje 9 błędów `no-untyped-def` w liniach 49, 52, 55, 61, 126, 129, 132, 138.

```bash
sed -n '45,65p' custom_components/thessla_green_modbus/scanner_device_info.py
sed -n '120,140p' custom_components/thessla_green_modbus/scanner_device_info.py
```

Dla każdej funkcji bez adnotacji dodaj typy argumentów i zwrotu. Typowe przypadki:
- `def _foo(self):` → `def _foo(self) -> None:`
- `def _bar(self, data):` → `def _bar(self, data: dict[str, Any]) -> bool:`
- `def _baz(self, reg):` → `def _baz(self, reg: RegisterDef) -> dict[str, Any]:`

Jedna dodatkowa uwaga z linii 124: `Incompatible return value type (got "dict[str, Any] | None", expected "dict[str, Any]")`. Tu albo popraw adnotację zwrotną na `dict[str, Any] | None`, albo dodaj early return zapewniający non-None.

---

## Weryfikacja końcowa

Po zastosowaniu wszystkich fixów:

```bash
# Expected: 343 → <20 mypy errors (reszta to edge-cases warte osobnego ticketu)
mypy custom_components/thessla_green_modbus/ 2>&1 | grep -c 'error:'

# Expected: "All checks passed!"
ruff check custom_components/thessla_green_modbus/ tests/ tools/

# Expected: 1604 passed (stan z v2 audytu)
pytest tests/ -x -q
```

**Akceptowalne pozostałości** (~10-20 błędów mypy):
- `scanner_core.py` — bardzo duża klasa (102K), może wymagać osobnego refactoru na mixiny.
- `config_flow.py` — 25 błędów, głównie voluptuous schema narrowing (mypy słabo radzi sobie z `vol.Schema`).
- edge-case `no-any-return` gdzie faktycznie wracamy `Any` bez możliwości zwężenia.

Wszystkie pozostałości udokumentuj w `pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = [
    "custom_components.thessla_green_modbus.scanner_core",
    "custom_components.thessla_green_modbus.config_flow",
]
disallow_untyped_defs = false  # TODO: address in separate PR
```

…żeby CI nie padał przy reszcie.

---

## Bump wersji i CHANGELOG

**Plik:** `custom_components/thessla_green_modbus/manifest.json`
```json
"version": "2.3.2",
```

**Plik:** `pyproject.toml`
```toml
version = "2.3.2"
```

**Plik:** `CHANGELOG.md` — dodaj na górze (po nagłówku, przed sekcją 2.3.1):
```markdown
## 2.3.2

### Changed
- Replaced runtime `getattr(ha_components, ...)` dispatch in `climate.py` with direct imports from `homeassistant.components.climate`. The fallback path was unreachable given the manifest-required HA version (2026.1.0) and produced 34 spurious mypy errors.
- Added missing attribute and method stub declarations on coordinator mixins (`_ModbusIOMixin`, `_CoordinatorScheduleMixin`, `_CoordinatorCapabilitiesMixin`) and scanner mixins (`_ScannerRegistersMixin`, `_ScannerTransportMixin`, `_ScannerCapabilitiesMixin`) so mypy can type-check them in isolation.
- Added explicit `assert self.client is not None` after `ensure_connected()` in `modbus_transport.py` I/O methods. Runtime behavior unchanged; enables mypy narrowing.
- Aligned signatures of conditional import fallback stubs in `scanner_register_maps.py`, `const.py`, `mappings/_helpers.py`, and `mappings/_loaders.py` with their real counterparts from `registers/loader.py`.
- Refactored BCD clock decode in `_coordinator_capabilities.py` to use explicit `and` chain instead of `all(generator)`, enabling mypy to narrow `None` from register reads.

### Fixed
- Mypy strict check now passes with ~10-20 errors (down from 343), unblocking CI typing stage.
- Cleaned up stale `# type: ignore[...]` comments that no longer applied after refactoring.
```

---

## Notatki końcowe

**Czego **nie** robimy w tym fixie (odkładamy na osobne PR-y):**

1. **Refactor monolitycznego `scanner_core.py` (102K).** To było w audycie v1 jako planowany refactor i jest ważne, ale zmienia zakres tego ticketu. Zrób osobny `CLAUDE_CODE_FIXES_SCANNER_SPLIT.md`.
2. **Refactor `__init__.py` (44K).** Analogicznie.
3. **Zwiększenie pokrycia testów dla `coordinator.py`.** Sugerowany cel (z v1 audytu: ≥90% na critical paths) wymaga osobnej pracy.
4. **Ewaluacja alternatywnego podejścia A (Protocol pattern)** zamiast atrybutów na mixinie. Protocol daje lepszą separację, ale wprowadza duplikację sygnatur. Decyzję warto podjąć po zmierzeniu kosztu utrzymania podejścia B przez 2-3 releasy.

**Co zyskujemy po v2.3.2:**
- CI pipeline z mypy strict w zielonym stanie (po wykluczeniu 2 plików z listą TODO).
- Mixiny coordinator/scanner są self-documenting — ktoś czytający `_coordinator_io.py` widzi od razu, jakich atrybutów rodzica oczekuje mixin, bez skakania do `coordinator.py` i `__init__`.
- Realne narrowing w `modbus_transport.py` — przypadek gdy `ensure_connected` padnie cicho i zwróci bez ustawienia klienta jest teraz złapany przez `assert` (w debug mode) zamiast rzucać `AttributeError: 'NoneType' object has no attribute 'read_input_registers'` kilka linijek dalej z mylącym stack trace.

**Ryzyko regresu:** minimalne. Wszystkie zmiany są czysto typowe (adnotacje, guardy), runtime behavior nie zmienia się. Jedyna realna zmiana semantyki to Fix #1 — usunięcie `getattr` fallbacku w `climate.py`. Jeśli ktoś uruchamiał testy bez HA w venv, fallback był potrzebny — ale `pytest-homeassistant-custom-component` (obecny w `requirements-dev.txt`) dostarcza HA, więc żaden realny use-case nie ucierpi.
