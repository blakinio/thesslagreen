# thessla_green_modbus — instrukcja napraw dla Claude Code (v9)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main` (HEAD: `cb2a33d` — merge PR #1329)
**Wersja docelowa:** `2.4.1 → 2.4.2`
**Data audytu:** 2026-04-17

---

## Co ten audyt odkrywa

Po pobraniu świeżego repo okazało się że:

✅ **V8 wdrożone** (PR #1329): `_compat_asdict` usunięty, `_HAS_HA + "pytest" in sys.modules` usunięte, `inspect.signature` w 3 miejscach usunięty, `"Skipping in mock context"` usunięte, trywialne `_schema`/`_required` usunięte.

✅ **Bonus — Fix #10 i #11 z v8 Grupa B wdrożone**:
- `_setup.py` wydzielony z `__init__.py` (246 linii) → `__init__.py` schudł z 1067 do **755 linii**.
- `scanner/core.py` podzielony: **1596 → 1043 linie** (−553), nowe moduły `scanner/orchestration.py` (385 linii) i `scanner/setup.py` (151 linii).

✅ **Fix #9 z v8 Grupa B wdrożone częściowo**: `CoordinatorConfig` dataclass istnieje, z metodą `from_entry(entry)` i factory `from_config(hass, config, entry)`. **ALE** nie usunięto 24-param `__init__` coordynatora — `from_config` to tylko wrapper który mapuje config na stary `__init__`.

🚨 **REGRESJA** — część pracy z v7 została **cofnięta**:
- `_compat.py` wrócił do 75 linii z `try/except ImportError` i fallbackami (po v7 miał być tylko re-exportem)
- `config_flow.py` odzyskał `DhcpServiceInfo`/`ZeroconfServiceInfo`/`ConfigFlowResult` fallbacki (v7 Fix #14a-b)
- `const.py` odzyskał `PLATFORMS` fallback (v7 Fix #5)
- `register_map.py` dodał `except (ImportError, ModuleNotFoundError): def get_all_registers(): return []` fallback

🚨 **NOWY SMELL krytyczny** — `_setup.py:40-48`:
```python
def _supports_typed_factory(coordinator_cls):
    if not hasattr(coordinator_cls, "from_config"): return False
    from unittest.mock import Mock
    return not isinstance(coordinator_cls, Mock)
```
**Produkcja sprawdza czy klasa jest `Mock`-iem**. Jeśli tak — wraca do starej ścieżki 22-kwarg. Nowy detox hack który zamiast usunąć, tylko skomplikował problem.

**Baseline:**
- ✅ Ruff: 0 findings
- ✅ Mypy strict: 0 errors (53 pliki — +3 od v2.4.0)
- ✅ Zero TODO/FIXME/HACK

---

## Motywacja v2.4.2

Dwa cele:

1. **Naprawa regresji** — przywrócenie stanu `_compat.py`/`config_flow.py` z v7 (czyste re-exports).
2. **Nowy detox** — usunięcie `_supports_typed_factory` Mock check + finalna unifikacja ścieżki konstrukcji coordynatora.

**Plus kilka nowych drobnych znalezisk** (sys.modules hacks w `mappings/`, test-compat komentarze w `modbus_helpers.py`).

**Minor bump (2.4.2)** — czysto removals/cleanups, zero feature changes.

---

## Zakres i kolejność

**Grupa A — Detox regresji (średnie ryzyko, każdy pojedyńczo):**

1. **Fix #1** — `_supports_typed_factory` + dual path w `async_create_coordinator` → jedna ścieżka przez `from_config`
2. **Fix #2** — `_compat.py` — powrót do czystych re-exports z v7
3. **Fix #3** — `config_flow.py` — usunięcie fallback `DhcpServiceInfo`/`ZeroconfServiceInfo`/`ConfigFlowResult`
4. **Fix #4** — `const.py` — usunięcie `PLATFORMS` fallback
5. **Fix #5** — `register_map.py` — usunięcie `get_all_registers` fallback

**Grupa B — Nowe znaleziska (niskie ryzyko):**

6. **Fix #6** — `modbus_helpers.py:285` — usunięcie komentarza + signature-based Mock workaround
7. **Fix #7** — `mappings/_loaders.py`/`legacy.py`/`_helpers.py` — audit wzorca `_get_parent()` z `sys.modules`

**Grupa C — Dokończenie Fix #9 z v8 (rekomendowane, niskie ryzyko):**

8. **Fix #8** — Uproszczenie 24-param `__init__` coordynatora przez prawdziwe użycie `CoordinatorConfig`

Po każdym fixie:
```bash
ruff check custom_components/ tests/ tools/
mypy custom_components/thessla_green_modbus/
pytest tests/ -x -q
```

---

## Fix #1 — Usuń `_supports_typed_factory` Mock check

**Plik:** `custom_components/thessla_green_modbus/_setup.py`

**Dowód (linie 40-48):**
```python
def _supports_typed_factory(coordinator_cls: Any) -> bool:
    """Return True when class can safely use from_config in runtime."""
    if not hasattr(coordinator_cls, "from_config"):
        return False
    try:
        from unittest.mock import Mock
    except ImportError:  # pragma: no cover
        return True
    return not isinstance(coordinator_cls, Mock)
```

**Co to robi:** sprawdza czy `coordinator_cls`:
1. Ma atrybut `from_config` (tak, **zawsze** ma — jest classmethod na `ThesslaGreenModbusCoordinator`).
2. **Nie jest instancją `Mock`**. Jeśli jest Mockiem → zwraca `False` → idziemy starą ścieżką 22-kwarg.

**Produkcja importuje `unittest.mock` w hot path** żeby wykryć testy. To jest **dokładnie ten sam gatunek smelli** który usuwaliśmy w v6/v8: produkcja-pod-testy.

**Dual code path w `async_create_coordinator` (linie 132-159):**
```python
if _supports_typed_factory(ThesslaGreenModbusCoordinator):
    return ThesslaGreenModbusCoordinator.from_config(hass, config, entry=entry)

return ThesslaGreenModbusCoordinator(
    hass=hass,
    host=config.host,
    port=config.port,
    # ... 19 więcej kwargs
    entry=entry,
)
```

**Dlaczego to istnieje:** testy podstawiają `Mock()` jako `ThesslaGreenModbusCoordinator` w `_setup.py`. `Mock()` ma każdy atrybut (włącznie z `from_config`) i każdą metodę. Gdyby produkcja wywołała `Mock.from_config(hass, config, entry)`, mock dostałby 3 argumenty zamiast 22 kwargs — test weryfikujący "czy coordinator został utworzony z properties X, Y, Z" padłby.

**Prawidłowe rozwiązanie:** zmuszenie testów do używania `MagicMock(spec=ThesslaGreenModbusCoordinator)` (z `spec=` mock akceptuje tylko prawdziwe metody) lub prawdziwego coordynatora.

### Krok 1a — usuń `_supports_typed_factory`

**Plik:** `custom_components/thessla_green_modbus/_setup.py`

#### SZUKAJ (linie 40-48)
```python
def _supports_typed_factory(coordinator_cls: Any) -> bool:
    """Return True when class can safely use from_config in runtime."""
    if not hasattr(coordinator_cls, "from_config"):
        return False
    try:
        from unittest.mock import Mock
    except ImportError:  # pragma: no cover
        return True
    return not isinstance(coordinator_cls, Mock)
```

#### USUŃ (całość)

### Krok 1b — uprość `async_create_coordinator`

**Plik:** `custom_components/thessla_green_modbus/_setup.py`

#### SZUKAJ (linie 130-159)
```python
    scan_interval_seconds = _scan_interval_seconds(config.scan_interval)

    if _supports_typed_factory(ThesslaGreenModbusCoordinator):
        return ThesslaGreenModbusCoordinator.from_config(hass, config, entry=entry)

    return ThesslaGreenModbusCoordinator(
        hass=hass,
        host=config.host,
        port=config.port,
        slave_id=config.slave_id,
        name=config.name,
        connection_type=config.connection_type,
        connection_mode=config.connection_mode,
        serial_port=config.serial_port,
        baud_rate=config.baud_rate,
        parity=config.parity,
        stop_bits=config.stop_bits,
        timeout=config.timeout,
        retry=config.retry,
        backoff=config.backoff,
        backoff_jitter=config.backoff_jitter,
        force_full_register_list=config.force_full_register_list,
        scan_uart_settings=config.scan_uart_settings,
        deep_scan=config.deep_scan,
        safe_scan=config.safe_scan,
        skip_missing_registers=config.skip_missing_registers,
        max_registers_per_request=config.max_registers_per_request,
        scan_interval=timedelta(seconds=scan_interval_seconds),
        entry=entry,
    )
```

#### ZASTĄP
```python
    return ThesslaGreenModbusCoordinator.from_config(hass, config, entry=entry)
```

### Krok 1c — sprawdź czy `timedelta` jeszcze używana

```bash
grep -n "\btimedelta\b" custom_components/thessla_green_modbus/_setup.py
```

Jeśli nie — usuń `from datetime import timedelta` z nagłówka. Jeśli wciąż używana (np. w `_scan_interval_seconds`) — zostaw.

### Krok 1d — napraw testy

```bash
grep -rn "ThesslaGreenModbusCoordinator\s*=\s*Mock\|coordinator_cls\s*=\s*Mock" tests/ --include="*.py"
```

Dla każdego testu podstawiającego `Mock()` jako coordinator class:

```python
# Było (działało dzięki _supports_typed_factory który zwracał False):
mock_coordinator_cls = Mock()
monkeypatch.setattr("custom_components.thessla_green_modbus._setup.ThesslaGreenModbusCoordinator", mock_coordinator_cls)
await async_create_coordinator(hass, entry)
mock_coordinator_cls.assert_called_once_with(host="1.2.3.4", port=502, ...)

# Ma być (explicit spec, `from_config` activates):
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
mock_coordinator = MagicMock(spec=ThesslaGreenModbusCoordinator)
# Lub jeszcze lepiej:
mock_from_config = AsyncMock()
monkeypatch.setattr(ThesslaGreenModbusCoordinator, "from_config", mock_from_config)
await async_create_coordinator(hass, entry)
mock_from_config.assert_called_once_with(hass, config_object, entry=entry)
```

### Oczekiwany efekt
- −9 linii funkcji `_supports_typed_factory`
- −25 linii dual-path construction w `async_create_coordinator`
- Jedna ścieżka konstrukcji — jaśniejszy flow
- `unittest.mock` nie jest już importowany w produkcji

---

## Fix #2 — `_compat.py` powrót do czystych re-exports

**Plik:** `custom_components/thessla_green_modbus/_compat.py`

**Dowód (linie 10-53):**
```python
try:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import (
        EVENT_HOMEASSISTANT_STOP,
        PERCENTAGE,
        UnitOfElectricPotential,
        UnitOfPower,
        UnitOfTemperature,
        UnitOfTime,
        UnitOfVolumeFlowRate,
    )
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity import EntityCategory
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
    from homeassistant.util import dt as dt_util
except (ImportError, ModuleNotFoundError, AttributeError):  # pragma: no cover - test stubs
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity import EntityCategory
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
    from homeassistant.util import dt as dt_util

    EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"
    PERCENTAGE = "%"

    class UnitOfElectricPotential:  # type: ignore[no-redef]
        VOLT = "V"
    # ... więcej takich klas
```

**To jest nielogiczne:**
- `try` block importuje z 5 modułów HA.
- `except` block importuje z **dokładnie tych samych 5 modułów HA**, z wyjątkiem `homeassistant.const`.
- Jedyne co `except` robi inaczej: re-defines `EVENT_HOMEASSISTANT_STOP`, `PERCENTAGE`, `UnitOf*` jako lokalne klasy.

**Kiedy except trigger'uje:** tylko gdy `homeassistant.const` jest dostępne **częściowo** (brak `EVENT_HOMEASSISTANT_STOP` lub `UnitOf*`). Te symbole są w HA od 2022. Manifest wymaga HA 2026.1.0.

**Po v7 (Fix #5):** ten plik był czystym re-exportem bez `try/except`. Regresja.

### Krok 2 — przywróć stan z v7

**Plik:** `custom_components/thessla_green_modbus/_compat.py`

#### ZASTĄP cały plik
```python
"""Compatibility re-exports for Home Assistant symbols used across the integration.

Manifest requires homeassistant>=2026.1.0 and python>=3.13, so all fallbacks
for running without Home Assistant have been removed. This module is now a
single import point for HA symbols used across the integration.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

COORDINATOR_BASE = DataUpdateCoordinator[dict[str, Any]]

__all__ = [
    "COORDINATOR_BASE",
    "EVENT_HOMEASSISTANT_STOP",
    "PERCENTAGE",
    "UTC",
    "BinarySensorDeviceClass",
    "DataUpdateCoordinator",
    "DeviceInfo",
    "EntityCategory",
    "SensorDeviceClass",
    "SensorStateClass",
    "UnitOfElectricPotential",
    "UnitOfPower",
    "UnitOfTemperature",
    "UnitOfTime",
    "UnitOfVolumeFlowRate",
    "UpdateFailed",
    "dt_util",
]
```

### Oczekiwany efekt
- 75 → ~40 linii czystego re-exportu (jak po v7)
- Brak fallbacków dla symbolów które są w HA od 2022
- `datetime.UTC` z Python 3.13 (nie `dt.timezone.utc` z `# noqa`)

---

## Fix #3 — `config_flow.py` — usuń fallbacki HA service info

**Plik:** `custom_components/thessla_green_modbus/config_flow.py`

**Dowód (linie 25-110):**
```python
try:
    from homeassistant.config_entries import ConfigFlowResult
except (ImportError, ModuleNotFoundError):  # pragma: no cover - test stubs
    ConfigFlowResult = dict[str, Any]

# ...

if TYPE_CHECKING:
    from homeassistant.components.dhcp import DhcpServiceInfo
    from homeassistant.components.zeroconf import ZeroconfServiceInfo
else:
    try:
        from homeassistant.components.dhcp import DhcpServiceInfo
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - lightweight test stubs

        @dataclasses.dataclass
        class DhcpServiceInfo:
            macaddress: str | None = None
            ip: str | None = None

    try:
        from homeassistant.components.zeroconf import ZeroconfServiceInfo
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - lightweight test stubs

        @dataclasses.dataclass
        class ZeroconfServiceInfo:
            host: str | None = None
```

**To są te same fallbacki które usunęliśmy w v7 Fix #14a-b.** Wróciły.

### Krok 3a — usuń `ConfigFlowResult` fallback

#### SZUKAJ (linie 25-28)
```python
try:
    from homeassistant.config_entries import ConfigFlowResult
except (ImportError, ModuleNotFoundError):  # pragma: no cover - test stubs
    ConfigFlowResult = dict[str, Any]
```

#### ZASTĄP
```python
from homeassistant.config_entries import ConfigFlowResult
```

### Krok 3b — usuń `DhcpServiceInfo`/`ZeroconfServiceInfo` fallback

#### SZUKAJ (linie 91-110)
```python
if TYPE_CHECKING:
    from homeassistant.components.dhcp import DhcpServiceInfo
    from homeassistant.components.zeroconf import ZeroconfServiceInfo
else:
    try:
        from homeassistant.components.dhcp import DhcpServiceInfo
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - lightweight test stubs

        @dataclasses.dataclass
        class DhcpServiceInfo:
            macaddress: str | None = None
            ip: str | None = None

    try:
        from homeassistant.components.zeroconf import ZeroconfServiceInfo
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - lightweight test stubs

        @dataclasses.dataclass
        class ZeroconfServiceInfo:
            host: str | None = None
```

#### ZASTĄP
```python
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.zeroconf import ZeroconfServiceInfo
```

### Krok 3c — sprawdź `dataclasses` import

```bash
grep -n "dataclasses" custom_components/thessla_green_modbus/config_flow.py
```

Jeśli `dataclasses` był używany tylko w usuniętych fallbackach — usuń `import dataclasses` z nagłówka.

### Krok 3d — sprawdź `TYPE_CHECKING` guard

Jeśli fallbacki były jedynym użyciem `TYPE_CHECKING` w tym pliku — sprawdź czy guard potrzebny dla innych importów (class `_ConfigFlowBase` na linii 112 używa `TYPE_CHECKING`).

### Oczekiwany efekt
- −25 linii test-compat kodu
- `config_flow.py` z 1304 → ~1280 linii

---

## Fix #4 — `const.py` — usuń `PLATFORMS` fallback

**Plik:** `custom_components/thessla_green_modbus/const.py`

**Dowód (linie ~236-262):**
```python
try:
    from homeassistant.const import Platform as _Platform

    PLATFORMS: list[_Platform] = [
        _Platform.SENSOR,
        _Platform.BINARY_SENSOR,
        _Platform.CLIMATE,
        _Platform.FAN,
        _Platform.SELECT,
        _Platform.NUMBER,
        _Platform.SWITCH,
        _Platform.TEXT,
        _Platform.TIME,
    ]
except (ImportError, AttributeError):  # pragma: no cover - fallback for test environments
    PLATFORMS = [
        "sensor",
        "binary_sensor",
        "climate",
        "fan",
        "select",
        "number",
        "switch",
        "text",
        "time",
    ]
```

**HA `Platform` enum** istnieje od 2022. Fallback istnieje dla stubów testowych.

### Krok 4 — uprość

**Plik:** `custom_components/thessla_green_modbus/const.py`

#### SZUKAJ (cały blok try/except dla `PLATFORMS`)
```python
try:
    from homeassistant.const import Platform as _Platform

    PLATFORMS: list[_Platform] = [
        _Platform.SENSOR,
        # ...
    ]
except (ImportError, AttributeError):  # pragma: no cover - fallback for test environments
    PLATFORMS = [
        "sensor",
        # ...
    ]
```

#### ZASTĄP
```python
from homeassistant.const import Platform

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
]
```

### Oczekiwany efekt
- −12 linii
- `PLATFORMS` jest listą `Platform` enum zamiast `list[_Platform | str]` union

---

## Fix #5 — `register_map.py` — usuń loader fallback

**Plik:** `custom_components/thessla_green_modbus/register_map.py`

**Dowód (linie 22-28):**
```python
try:
    from .registers.loader import RegisterDef, get_all_registers
except (ImportError, ModuleNotFoundError):  # pragma: no cover - fallback for test stubs
    from typing import Any as RegisterDef  # type: ignore

    def get_all_registers():  # type: ignore
        return []
```

**Kiedy to trigger'uje:** tylko gdy ktoś wykomentuje `registers/loader.py` lub nie zainstaluje JSON-a. W produkcji **zawsze dostępne**.

**Problem z fallbackiem:** `def get_all_registers(): return []` zwraca pustą listę. Jeśli coś poszłoby nie tak z loaderem, integracja **uruchomi się z 0 rejestrami** zamiast rzucić błąd. Defensywa która maskuje bug.

### Krok 5 — usuń fallback

**Plik:** `custom_components/thessla_green_modbus/register_map.py`

#### SZUKAJ (linie 22-28)
```python
try:
    from .registers.loader import RegisterDef, get_all_registers
except (ImportError, ModuleNotFoundError):  # pragma: no cover - fallback for test stubs
    from typing import Any as RegisterDef  # type: ignore

    def get_all_registers():  # type: ignore
        return []
```

#### ZASTĄP
```python
from .registers.loader import RegisterDef, get_all_registers
```

### Krok 5b — napraw testy

Testy które polegały na pustym loaderze:
```python
# Źle:
monkeypatch.setattr("custom_components.thessla_green_modbus.registers.loader.get_all_registers", lambda: [])

# Jeśli test potrzebuje custom register list:
monkeypatch.setattr(
    "custom_components.thessla_green_modbus.registers.loader.get_all_registers",
    lambda: [custom_register_1, custom_register_2]
)
```

### Oczekiwany efekt
- −6 linii
- Jeśli `loader.py` zepsuty → błąd jawny przy imporcie, nie cicha pusta lista

---

## Fix #6 — `modbus_helpers.py` — usuń Mock-oriented signature workaround

**Plik:** `custom_components/thessla_green_modbus/modbus_helpers.py`

**Dowód (linie 280-289):**
```python
        elif "slave" in params and params["slave"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "slave"
        elif "unit" in params and params["unit"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "unit"
        else:
            # Some tests use plain ``Mock``/``AsyncMock`` callables that do not
            # expose a valid signature. Prefer ``slave`` as default because it
            # matches modern pymodbus and is accepted by autospecced mocks.
            kwarg = "slave" if signature is None else ""
        _KWARG_CACHE[func] = kwarg
```

**Kontekst:** `modbus_helpers._call_modbus` dynamicznie wykrywa czy funkcja pymodbus akceptuje `device_id`/`slave`/`unit` jako kwarg (zmiana API w pymodbus 3.x). Signature inspection jest uzasadnione dla real-world zgodności z różnymi wersjami pymodbus.

**Co jest smellem:** specific fallback `kwarg = "slave" if signature is None else ""` z komentarzem o Mock/AsyncMock.

**Czy to naprawdę smell:**
- Produkcyjnie `signature` zwraca valid signature dla pymodbus funkcji.
- `signature is None` może się zdarzyć gdy `inspect.signature` rzuci wyjątek — w teorii może się to zdarzyć dla niektórych C-extension funkcji.
- Ale komentarz jasno wskazuje że fallback jest **dla testów**.

### Krok 6 — uprość komentarz i fallback

**Plik:** `custom_components/thessla_green_modbus/modbus_helpers.py`

#### SZUKAJ (linie 280-289)
```python
        elif "slave" in params and params["slave"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "slave"
        elif "unit" in params and params["unit"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "unit"
        else:
            # Some tests use plain ``Mock``/``AsyncMock`` callables that do not
            # expose a valid signature. Prefer ``slave`` as default because it
            # matches modern pymodbus and is accepted by autospecced mocks.
            kwarg = "slave" if signature is None else ""
        _KWARG_CACHE[func] = kwarg
```

#### ZASTĄP
```python
        elif "slave" in params and params["slave"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "slave"
        elif "unit" in params and params["unit"].kind is not inspect.Parameter.POSITIONAL_ONLY:
            kwarg = "unit"
        else:
            # Default to "slave" when signature introspection failed — matches
            # pymodbus 3.x convention. Pass no kwarg when signature is available
            # but neither device_id/slave/unit is recognized.
            kwarg = "slave" if signature is None else ""
        _KWARG_CACHE[func] = kwarg
```

Zmiana to tylko refactor komentarza — usunięcie wzmianki o Mockach w produkcji. Logika pozostaje (bo jest legitymacznie potrzebna dla pymodbus C-extensions).

### Oczekiwany efekt
- Komentarze produkcyjne mówią o **produkcyjnych scenariuszach**, nie o tym jak kod obsługuje mocki testów.
- Zero funkcjonalnej zmiany.

---

## Fix #7 — Audit `_get_parent()` pattern w `mappings/`

**Pliki:**
- `custom_components/thessla_green_modbus/mappings/_loaders.py`
- `custom_components/thessla_green_modbus/mappings/legacy.py`
- `custom_components/thessla_green_modbus/mappings/_helpers.py`

**Dowód z `mappings/_loaders.py:48-65`:**
```python
def _get_parent() -> Any:
    """Return the parent mappings package module.

    Using ``sys.modules`` lookup allows test monkeypatching on the parent
    module (e.g. ``monkeypatch.setattr(em, "get_all_registers", ...)``) to
    transparently propagate into the functions below.
    """
    return sys.modules.get(__package__)


def _resolve(attr: str, fallback: Any) -> Any:
    """Look up *attr* on the parent mappings module, falling back to *fallback*."""
    parent = _get_parent()
    if parent is not None:
        val = getattr(parent, attr, None)
        if val is not None:
            return val
    return fallback


def _load_number_mappings() -> dict[str, dict[str, Any]]:
    _get_all = _resolve("get_all_registers", get_all_registers)
    _get_info = _resolve("_get_register_info", _get_register_info)
    _parse = _resolve("_parse_states", _parse_states)
    # ...
```

**Co to robi:** `_resolve` przy każdym wywołaniu `_load_number_mappings()` sprawdza moduł nadrzędny `mappings` w `sys.modules`, próbuje znaleźć zmienioną (patched) wersję funkcji, i jeśli jest — używa jej zamiast lokalnie zaimportowanej.

**Dlaczego to istnieje:** testy robią:
```python
import custom_components.thessla_green_modbus.mappings as em
monkeypatch.setattr(em, "get_all_registers", custom_registers_func)
em._load_number_mappings()  # chce użyć custom_registers_func
```

**Rzeczywiście uzasadnione jednak:** **jest to akceptowalne.** Bez tego wzorca monkey-patch na parent module nie propagowałby się do loadera. To NIE jest smell — to rozsądny wzorzec dla **testowalności**.

**ALE**: komentarze które są smellami:
```python
# Comment in mappings/_helpers.py:
# monkeypatching on the parent module so that test monkeypatching on 
# ``em._REGISTER_INFO_CACHE`` is still visible
```

**Decyzja:** Pattern jest legit. **Nie ruszamy**. Ale wartościowe jest **udokumentowanie decyzji** — żeby następny audyt wiedział że to NIE jest smell do usunięcia.

### Krok 7 — dodaj komentarz decision-doc

**Plik:** `custom_components/thessla_green_modbus/mappings/_loaders.py`

#### SZUKAJ (linia 48)
```python
def _get_parent() -> Any:
    """Return the parent mappings package module.

    Using ``sys.modules`` lookup allows test monkeypatching on the parent
    module (e.g. ``monkeypatch.setattr(em, "get_all_registers", ...)``) to
    transparently propagate into the functions below.
    """
    return sys.modules.get(__package__)
```

#### ZASTĄP
```python
def _get_parent() -> Any:
    """Return the parent mappings package module for attribute resolution.

    Design note: all loaders in this module resolve attributes via the parent
    package rather than direct imports. This is intentional — it allows tests
    to patch attributes on the ``mappings`` package and have those patches
    visible to loaders without monkey-patching each individual private function.

    This is NOT a test-induced production smell; it is a deliberate design
    choice for module-level indirection. The pattern is established and
    documented here to prevent accidental removal in future audits.
    """
    return sys.modules.get(__package__)
```

### Oczekiwany efekt
- Zero kodowej zmiany
- Jasne oznaczenie "to jest zamierzone, nie usuwaj"
- Ochrona przed błędnym fixem w kolejnym audycie

---

## Fix #8 — Prawdziwe uproszczenie 24-param `__init__` coordynatora

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Kontekst:** `CoordinatorConfig` dataclass istnieje (linia 130). `from_config` factory istnieje (linia 383). Ale `ThesslaGreenModbusCoordinator.__init__` wciąż ma **24 parametry** (linia ~200). `from_config` to **wrapper** który dekonstruuje `config` na 22 kwargs i przekazuje do `__init__`.

**Właściwy refactor:** `__init__` przyjmuje `CoordinatorConfig` zamiast 24 kwargs.

**Dowód obecnego stanu:**

```python
# Linia ~200 - 24 parametry
def __init__(
    self,
    hass: HomeAssistant,
    host: str,
    port: int,
    slave_id: int,
    name: str = DEFAULT_NAME,
    scan_interval: timedelta | int = DEFAULT_SCAN_INTERVAL,
    # ... 18 więcej
    stop_bits: int = DEFAULT_STOP_BITS,
) -> None:

# Linia ~383 - wrapper robi dokładnie to samo
@classmethod
def from_config(cls, hass, config, *, entry=None) -> ThesslaGreenModbusCoordinator:
    return cls(
        hass=hass,
        host=config.host,
        port=config.port,
        # ... 21 więcej
        stop_bits=config.stop_bits,
    )
```

**Idealny stan docelowy:**
```python
def __init__(
    self,
    hass: HomeAssistant,
    config: CoordinatorConfig,
    *,
    entry: ConfigEntry | None = None,
) -> None:
    # Body używa self.config.host etc. zamiast self.host

@classmethod
def from_config(cls, hass, config, *, entry=None) -> ThesslaGreenModbusCoordinator:
    return cls(hass, config, entry=entry)  # trywialne, można usunąć
```

**ALE** — to jest **większy refactor**:
- Body `__init__` używa `self.host`, `self.port` etc. (ustawiane w linii ~200-260).
- Mixiny coordynatora (`_ModbusIOMixin`, `_CoordinatorCapabilitiesMixin`, `_CoordinatorScheduleMixin`) prawdopodobnie używają `self.host` etc. bezpośrednio.
- Testy tworzące coordinator z kwargs musiałyby zostać przepisane.

**Ryzyko:** ŚREDNIE-WYSOKIE. To major bump (breaking change publicznego API klasy).

### Opcja A — Minimalna refactor (rekomendowana dla 2.4.2)

**Zostaw `__init__` jak jest, ale zapisz `config` jako atrybut:**

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

W `__init__` na końcu (po ustawieniu wszystkich `self.*`):

#### SZUKAJ (koniec `__init__`, po wszystkich `self.X = X`)
```python
        # Initialize other coordinator state
        self._total_energy = 0.0
```

(lub ostatnia linia inicjalizacji w `__init__`)

#### ZASTĄP (dodaj przed/po)
```python
        # Initialize other coordinator state
        self._total_energy = 0.0

        # Store normalized config for access by mixins and external code.
        # This is a read-only snapshot of the initialization parameters —
        # mutations should happen via explicit methods, not via config.X = ...
        self.config = CoordinatorConfig(
            host=host,
            port=port,
            slave_id=slave_id,
            name=name,
            scan_interval=scan_interval,
            timeout=timeout,
            retry=retry,
            backoff=backoff,
            backoff_jitter=backoff_jitter,
            force_full_register_list=force_full_register_list,
            scan_uart_settings=scan_uart_settings,
            deep_scan=deep_scan,
            safe_scan=safe_scan,
            max_registers_per_request=max_registers_per_request,
            skip_missing_registers=skip_missing_registers,
            connection_type=connection_type,
            connection_mode=connection_mode or CONNECTION_MODE_AUTO,
            serial_port=serial_port,
            baud_rate=baud_rate,
            parity=parity,
            stop_bits=stop_bits,
        )
```

**Efekt:** `coordinator.config` jest dostępne jako `CoordinatorConfig` dataclass, ale stare atrybuty (`coordinator.host`, `coordinator.port`) **pozostają** — zero breaking change.

### Opcja B — Pełny refactor (odłożone na 2.5.0)

Odłożyć do 2.5.0 major bump:
1. Zmiana `__init__` na `def __init__(self, hass, config: CoordinatorConfig, *, entry=None)`.
2. Aktualizacja wszystkich odwołań `self.host` → `self.config.host` (podobnie dla 22 atrybutów).
3. Aktualizacja wszystkich testów konstruujących coordinator (10+ miejsc w `tests/test_coordinator.py`).
4. `from_config` staje się trywialnym `return cls(hass, config, entry=entry)`.

**Decyzja dla 2.4.2:** Opcja A. Coordinator ma `self.config` dostępne dla mixinów i zewnętrznego kodu, ale 24-param `__init__` pozostaje (zamrożony API). Fix #1 (usunięcie `_supports_typed_factory`) robi z `from_config` jedyną ścieżkę konstrukcji w produkcji.

### Oczekiwany efekt
- `coordinator.config` nowy atrybut jako `CoordinatorConfig`
- Zero breaking change dla callerów używających `coordinator.host` etc.
- Foundation pod Opcję B w 2.5.0

---

## Weryfikacja końcowa

Po zastosowaniu Fixów #1-#8:

```bash
ruff check custom_components/ tests/ tools/      # Expected: All checks passed!
mypy custom_components/thessla_green_modbus/     # Expected: Success: 53 source files
pytest tests/ -x -q                               # Expected: po napraw testów wszystko przechodzi
python tools/compare_registers_with_reference.py # Expected: pass
```

**Metryki:**

```
                                v2.4.1       v2.4.2 (target)
_supports_typed_factory:           ✗ (exists)   ✓ (removed)
_compat.py test fallback:         Present      Removed
config_flow.py HA fallbacks:      Present      Removed
const.py PLATFORMS fallback:      Present      Removed
register_map.py loader fallback:  Present      Removed
Production imports unittest.mock:  1            0
Production sys.modules hacks:      4 (shim+3 mappings pattern)   3 (mappings pattern udokumentowany)
coordinator.config attribute:      No          Yes (nowy)
```

---

## Bump wersji i CHANGELOG

**Plik:** `custom_components/thessla_green_modbus/manifest.json`
```json
"version": "2.4.2",
```

**Plik:** `pyproject.toml`
```toml
version = "2.4.2"
```

**Plik:** `CHANGELOG.md` — dodaj na górze:
```markdown
## 2.4.2 — Detox regression fixes

Fixes several test-compat fallbacks that had crept back into production code
after the 2.4.1 detox, and completes the `CoordinatorConfig` refactor started
in 2.4.1.

### Removed
- `_supports_typed_factory` function and dual-path coordinator construction in `_setup.async_create_coordinator`. Production code no longer imports `unittest.mock.Mock` at runtime; `from_config` is the single code path.
- `try/except ImportError` fallbacks in `_compat.py`. `__compat.py` is now a pure re-export module as intended after v2.4.0.
- `DhcpServiceInfo` / `ZeroconfServiceInfo` / `ConfigFlowResult` fallback imports in `config_flow.py`. These HA symbols are stable; direct imports are used.
- `PLATFORMS` string-list fallback in `const.py`. Direct `Platform` enum is used.
- `get_all_registers()` fallback in `register_map.py`. Register loader failure now raises `ImportError` explicitly instead of returning an empty register list.

### Changed
- Comment in `modbus_helpers._get_kwarg_for_slave` updated to describe production behavior (pymodbus C-extensions) instead of referring to test Mock handling.
- Added design-note docstring on `mappings/_loaders._get_parent` explaining that the `sys.modules`-based attribute resolution pattern is intentional and should not be removed in future audits.

### Added
- `ThesslaGreenModbusCoordinator.config` attribute — a `CoordinatorConfig` dataclass snapshot of initialization parameters. This is a non-breaking addition; existing `coordinator.host`, `coordinator.port` etc. attributes continue to work.

### Migration notes
- Tests that replaced `ThesslaGreenModbusCoordinator` with a plain `Mock()` for `async_create_coordinator` will now fail because `from_config` is called unconditionally. Use `MagicMock(spec=ThesslaGreenModbusCoordinator)` or patch `from_config` explicitly.
- Tests that monkey-patched `get_all_registers` to return `[]` at import time will now fail at import. Patch at test setup time using `monkeypatch.setattr`.
```

---

## Odłożone na 2.5.0 (major bump)

**Fix #9 — Pełny refactor `__init__` → `def __init__(self, hass, config)`.**
- Change signature from 24-param to 2-param.
- Update all `self.host` → `self.config.host` (i 22 podobnych).
- Update all test constructors (10+ miejsc).
- Usunąć `from_config` wrapper (redundant).

**Fix #10 — Dalsza redukcja `coordinator.py` (1617 linii).**
Kandydaci do extraktu:
- `_handle_update_error` (w coordinator.py) → potencjalnie do `_coordinator_io.py`.
- Register-reading logic w `_async_update_data` → delegacja do mixinów lepsza.

**Fix #11 — Dalszy podział `__init__.py` (755 linii).**
13 funkcji migracji/setup wciąż w jednym pliku:
- Nowy `_migrations.py` — `_async_migrate_unique_ids`, `_async_migrate_entity_ids`, `_async_cleanup_legacy_fan_entity`, `async_migrate_entry`.
- Nowy `_legacy.py` — legacy entity ID mapping.

**Fix #12 — Redukcja `# pragma: no cover` w całym codebase.**
Obecnie 33 plików z `# pragma: no cover`. Każde jedno wystąpienie powinno mieć uzasadnienie — "test env" lub "defensive" (nie testowalne łatwo). Audit dla każdego.

---

## Notatki końcowe

**Dlaczego to minor bump (2.4.2):**
- Fixy są czysto removalami/cleanupami, zero nowych funkcji.
- `coordinator.config` atrybut to dodawanie non-breaking (stare atrybuty pozostają).
- Brak breaking changes w publicznym API.

**Ryzyko regresu — niskie-średnie:**
- Fix #1 — ryzyko ze testy z `Mock()` coordynatora będą padać → naprawić używając `spec=`.
- Fix #2-5 — ryzyko że jakieś środowisko testowe bez pełnego HA padało z `ImportError` → używać `pytest-homeassistant-custom-component`.
- Fix #6-7 — zero ryzyka, same komentarze.
- Fix #8 — czysto additive, zero ryzyka.

**Strategia wdrożenia:**
- **Commit 1**: Fix #1 (najbardziej spektakularny — produkcja nie importuje `unittest.mock`).
- **Commit 2**: Fix #2-5 (restore v7 state dla plików które cofnęły się).
- **Commit 3**: Fix #6-7 (komentarze).
- **Commit 4**: Fix #8 (`coordinator.config` atrybut).
- Tag **2.4.2**.

**Co ten audyt wykrywa:** przypadek gdzie **fixy z v7 częściowo się cofnęły** w czasie implementacji kolejnych PR-ów. To normalne dla dużych PR-ów mergowanych bez pełnej code review — autor PR #1328 (wdrażającego v7) prawdopodobnie miał konflikty z innymi zmianami i wrócił do starszej wersji niektórych plików. Ten audyt przywraca intencję v7 + dodaje dwa nowe znaleziska (`_supports_typed_factory`, `coordinator.config`).

**Długofalowo:** warto by skrypt w CI sprawdzał "anti-regression" — listę wzorców które zostały usunięte i nie powinny wrócić. Np.:
```bash
# W CI:
if grep -rn "from unittest.mock" custom_components/thessla_green_modbus/ --include="*.py"; then
    echo "ERROR: unittest.mock imported in production code"
    exit 1
fi
```

To by wyłapało dziesiątki smelli automatycznie zanim trafią do głównej gałęzi.
