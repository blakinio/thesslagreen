# CLAUDE.md — thessla_green_modbus implementation guide

Repozytorium: https://github.com/blakinio/thesslagreen
Integracja: `custom_components/thessla_green_modbus/`

Wykonuj zadania w kolejności. Po każdym BLOKU uruchom testy:
```bash
cd tests && python -m pytest -x -q 2>&1 | tail -20
```
Jeśli testy nie przechodzą — zatrzymaj się i napraw zanim przejdziesz dalej.

---

## BLOK 1 — HA 2026: hass.data → entry.runtime_data

Dotyczy 12 plików. Zmiana jest mechaniczna — nie zmienia logiki.

### `__init__.py`

**Zmiana 1 — dodaj type alias po importach (przed pierwszą funkcją):**

SZUKAJ (linia ~78):
```python
_LOGGER = logging.getLogger(__name__)
```
ZASTĄP:
```python
_LOGGER = logging.getLogger(__name__)

type ThesslaGreenConfigEntry = ConfigEntry["ThesslaGreenModbusCoordinator"]
```

**Zmiana 2 — zapis coordinatora:**

SZUKAJ:
```python
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
```
ZASTĄP:
```python
    # Store coordinator on entry (HA 2024.6+ pattern)
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})
```

**Zmiana 3 — sprawdzenie czy serwisy już załadowane:**

SZUKAJ:
```python
    # Setup services (only once for first entry)
    if len(hass.data[DOMAIN]) == 1:
        from .services import async_setup_services

        await async_setup_services(hass)
```
ZASTĄP:
```python
    # Setup services (only once for first entry)
    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        from .services import async_setup_services

        await async_setup_services(hass)
```

**Zmiana 4 — update listener:**

SZUKAJ:
```python
    # Setup entry update listener
    add_listener = getattr(entry, "add_update_listener", None)
    async_on_unload = getattr(entry, "async_on_unload", None)
    if callable(add_listener) and callable(async_on_unload):
        async_on_unload(add_listener(async_update_options))
```
ZASTĄP:
```python
    # Setup entry update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
```

**Zmiana 5 — unload:**

SZUKAJ:
```python
    if unload_ok:
        # Shutdown coordinator
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()

        # Remove from hass data
        hass.data[DOMAIN].pop(entry.entry_id)

        # Clean up domain data if no more entries
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            # Unload services when last entry is removed
            from .services import async_unload_services

            await async_unload_services(hass)
```
ZASTĄP:
```python
    if unload_ok:
        # Shutdown coordinator
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()

        # Unload services when last entry is removed
        if not hass.config_entries.async_entries(DOMAIN):
            from .services import async_unload_services

            await async_unload_services(hass)
```

**Zmiana 6 — async_update_options:**

SZUKAJ:
```python
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
```
ZASTĄP:
```python
    coordinator = getattr(entry, "runtime_data", None)
```

**Zmiana 7 — _async_migrate_unique_ids:**

SZUKAJ:
```python
    coordinator = hass.data[DOMAIN][entry.entry_id]
```
ZASTĄP (w funkcji _async_migrate_unique_ids):
```python
    coordinator = entry.runtime_data
```

---

### Wszystkie platformy — jednolity wzorzec

W każdym z poniższych plików wykonaj dokładnie **jedną** zamianę:

**`sensor.py` linia 77:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
```
Dodaj import na górze pliku (jeśli nie ma):
```python
from .coordinator import ThesslaGreenModbusCoordinator
```

**`binary_sensor.py` linia 42:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
```

**`climate.py` linia 79:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
```

**`fan.py` linia 35:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data
```

**`number.py` linia 45:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data
```

**`select.py` linia 39:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
```

**`switch.py` linia 33:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data
```

**`text.py` linia 38:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
```

**`time.py` linia 39:**
```python
# SZUKAJ:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data
```

**`diagnostics.py` linia 72:**
```python
# SZUKAJ:
    coordinator: ThesslaGreenModbusCoordinator = hass.data[DOMAIN][entry.entry_id]
# ZASTĄP:
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data
```

W każdym pliku platformy usuń też import `DOMAIN` jeśli był używany **wyłącznie** do `hass.data[DOMAIN]` — sprawdź czy DOMAIN jest używane gdzieś indziej w tym samym pliku zanim usuniesz.

---

## BLOK 2 — HA 2026: FlowResult → ConfigFlowResult

### `config_flow.py`

**Zmiana importu (linia 21):**

SZUKAJ:
```python
from homeassistant.data_entry_flow import FlowResult
```
ZASTĄP:
```python
from homeassistant.config_entries import ConfigFlowResult
```

**Zamień wszystkie sygnatury** — wykonaj global find & replace w pliku:
- `-> FlowResult:` → `-> ConfigFlowResult:`

Dotyczy linii: 775, 849, 960, 1025, 1093, 1166.

---

## BLOK 3 — HA 2026: Platform enum

### `const.py`

**Zmiana (linia 188):**

SZUKAJ:
```python
# Platforms supported by the integration
# Diagnostics is handled separately and therefore not listed here
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
ZASTĄP:
```python
# Platforms supported by the integration
# Diagnostics is handled separately and therefore not listed here
from homeassistant.const import Platform  # noqa: E402 - placed here to avoid circular import

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

Sprawdź czy `Platform` jest już importowany wcześniej w `const.py`. Jeśli tak — usuń duplikat i przenieś import na górę pliku zamiast inline.

---

## BLOK 4 — MAX_REGISTERS domyślny limit

### `const.py` (linia 28)

SZUKAJ:
```python
MAX_REGISTERS_PER_REQUEST = 16
MAX_REGS_PER_REQUEST = MAX_REGISTERS_PER_REQUEST
MAX_BATCH_REGISTERS = MAX_REGISTERS_PER_REQUEST
```
ZASTĄP:
```python
# Modbus TCP spec allows up to 125 registers per request.
# 60 is a safe default for ThesslaGreen AirPack over TCP —
# reduces update cycle from ~25 requests to ~7 per poll.
# Users can lower this in options for problematic devices.
MAX_REGISTERS_PER_REQUEST = 60
MAX_REGS_PER_REQUEST = MAX_REGISTERS_PER_REQUEST
MAX_BATCH_REGISTERS = MAX_REGISTERS_PER_REQUEST
```

---

## BLOK 5 — Rejestr: literówka antifreez_stage

Zmiana dotyczy 4 plików. Wszędzie wykonaj find & replace:
`antifreez_stage` → `antifreeze_stage`

### `registers/thessla_green_registers_full.json` (linia 2339)

SZUKAJ:
```json
      "name": "antifreez_stage",
```
ZASTĄP:
```json
      "name": "antifreeze_stage",
```

### `entity_mappings.py` (linia ~785–786)

SZUKAJ:
```python
    "antifreez_stage": {
        "translation_key": "antifreez_stage",
```
ZASTĄP:
```python
    "antifreeze_stage": {
        "translation_key": "antifreeze_stage",
```

### `strings.json` (linia ~1051)

SZUKAJ:
```json
      "antifreez_stage": {
        "name": "Antifreeze Stage"
      },
```
ZASTĄP:
```json
      "antifreeze_stage": {
        "name": "Antifreeze Stage"
      },
```

### `translations/en.json` (linia ~1075)

SZUKAJ:
```json
      "antifreez_stage": {
        "name": "Antifreeze Stage",
        "state": {
          "off": "Off",
          "fpx1": "FPX Mode 1",
          "fpx2": "FPX Mode 2"
        }
      },
```
ZASTĄP:
```json
      "antifreeze_stage": {
        "name": "Antifreeze Stage",
        "state": {
          "off": "Off",
          "fpx1": "FPX Mode 1",
          "fpx2": "FPX Mode 2"
        }
      },
```

### `translations/pl.json` (linia ~1075)

SZUKAJ:
```json
      "antifreez_stage": {
        "name": "Faza ochrony przeciwzamrożeniowej",
        "state": {
          "off": "Wyłączona",
          "fpx1": "Tryb FPX1",
          "fpx2": "Tryb FPX2"
        }
      },
```
ZASTĄP:
```json
      "antifreeze_stage": {
        "name": "Faza ochrony przeciwzamrożeniowej",
        "state": {
          "off": "Wyłączona",
          "fpx1": "Tryb FPX1",
          "fpx2": "Tryb FPX2"
        }
      },
```

### Migracja unique_id dla istniejących instalacji

Ponieważ zmiana nazwy rejestru zmienia entity_id, dodaj alias do
`entity_mappings.py` w słowniku `LEGACY_ENTITY_ID_OBJECT_ALIASES` (linia ~119):

SZUKAJ:
```python
    "rekuperator_on_off_panel_mode": ("switch", "rekuperator_on_off_panel_mode"),
}
```
ZASTĄP:
```python
    "rekuperator_on_off_panel_mode": ("switch", "rekuperator_on_off_panel_mode"),
    # Typo fix: antifreez_stage → antifreeze_stage (version 2.3.0)
    "rekuperator_antifreez_stage": ("sensor", "rekuperator_antifreeze_stage"),
}
```

---

## BLOK 6 — Rejestr: nazwy urządzenia reserved_8145–8151

Scanner w `scanner_core.py` już poprawnie czyta 8 rejestrów od adresu 8144
(linia ~1137–1149) i dekoduje pełny string ASCII. Problem jest tylko w JSON —
rejestry 8145–8151 są oznaczone jako `reserved_*` zamiast `device_name_N`.

### `registers/thessla_green_registers_full.json`

Wykonaj 7 zamian (po jednej na rejestr). Wzorzec jest identyczny dla każdego:

**Rejestr 8145 (linia 3553):**
SZUKAJ:
```json
      "name": "reserved_8145",
      "access": "RW",
      "unit": null,
      "enum": null,
      "multiplier": 1,
      "resolution": 1,
      "description": "Nazwa urządzenia - część 2",
      "description_en": "Device name - part 2"
```
ZASTĄP:
```json
      "name": "device_name_2",
      "access": "RW",
      "unit": "ASCII",
      "enum": null,
      "multiplier": 1,
      "resolution": 1,
      "type": "string_part",
      "string_group": "device_name",
      "string_part_index": 2,
      "description": "Nazwa urządzenia - część 2",
      "description_en": "Device name - part 2"
```

**Rejestr 8146 (linia 3566):** tak samo, `reserved_8146` → `device_name_3`, `string_part_index: 3`

**Rejestr 8147 (linia 3579):** `reserved_8147` → `device_name_4`, `string_part_index: 4`

**Rejestr 8148 (linia 3592):** `reserved_8148` → `device_name_5`, `string_part_index: 5`

**Rejestr 8149 (linia 3605):** `reserved_8149` → `device_name_6`, `string_part_index: 6`

**Rejestr 8150 (linia 3618):** `reserved_8150` → `device_name_7`, `string_part_index: 7`

**Rejestr 8151 (linia 3631):** `reserved_8151` → `device_name_8`, `string_part_index: 8`

Uwaga: scanner_core.py już prawidłowo dekoduje całą nazwę z 8 rejestrów —
ta zmiana tylko koryguje metadane JSON żeby były zgodne ze specyfikacją.

---

## BLOK 7 — Usunięcie unittest.mock z kodu produkcyjnego

### `coordinator.py`

**Zmiana 1 — usuń import (linia 14):**

SZUKAJ:
```python
from unittest.mock import Mock
```
ZASTĄP:
```python
# (usunięto import unittest.mock — produkcja nie powinna zależeć od frameworku testowego)
```
Następnie usuń całą tę linię komentarza — zostaw tylko pusty wiersz.

**Zmiana 2 — disconnect_cb AsyncMock check (linia ~589):**

SZUKAJ:
```python
                elif callable(disconnect_cb) and disconnect_cb.__class__.__name__ == "AsyncMock":
                    await disconnect_cb()
```
ZASTĄP:
```python
                elif callable(disconnect_cb) and asyncio.iscoroutinefunction(disconnect_cb):
                    await disconnect_cb()
```

**Zmiana 3 — drugi disconnect_cb AsyncMock check (linia ~629):**

SZUKAJ:
```python
                elif callable(disconnect_cb) and disconnect_cb.__class__.__name__ == "AsyncMock":  # pragma: no cover
                    await disconnect_cb()
```
ZASTĄP:
```python
                elif callable(disconnect_cb) and asyncio.iscoroutinefunction(disconnect_cb):  # pragma: no cover
                    await disconnect_cb()
```

**Zmiana 4 — scanner_cls Mock check (linia ~735):**

SZUKAJ:
```python
                    if isinstance(scanner_cls, Mock) or hasattr(scanner_cls, "return_value"):
```
ZASTĄP:
```python
                    if not inspect.isclass(scanner_cls):
```

**Zmiana 5 — executor_job Mock check w _async_update_data (linia ~1384):**

SZUKAJ:
```python
        executor_job = getattr(self.hass, "async_add_executor_job", None)
        if callable(executor_job) and executor_job.__class__.__module__.startswith("unittest.mock"):
            maybe_result = executor_job(self._update_data_sync)
            compat_result = await maybe_result if inspect.isawaitable(maybe_result) else maybe_result
            if isinstance(compat_result, dict) and compat_result:
                return compat_result
```
ZASTĄP:
```python
        # (usunięto mock-detection — testy używają normalnego async_add_executor_job)
```
Usuń linię komentarza, zostaw tylko puste miejsce zachowując flow kodu.

**Zmiana 6 — executor_job Mock check w async_write_register (linia ~2101):**

SZUKAJ:
```python
        executor_job = getattr(self.hass, "async_add_executor_job", None)
        if callable(executor_job) and executor_job.__class__.__module__.startswith("unittest.mock"):
            maybe_result = executor_job(lambda: True)
            compat_result = await maybe_result if inspect.isawaitable(maybe_result) else maybe_result
            if isinstance(compat_result, bool):
                return compat_result
```
ZASTĄP:
```python
        # (usunięto mock-detection)
```
Podobnie — usuń komentarz, zachowaj puste miejsce.

### `config_flow.py`

**Zmiana 1 — usuń import (linia 15):**

SZUKAJ:
```python
from unittest.mock import Mock
```
USUŃ tę linię.

**Zmiana 2 — scan_is_mocked check (linia ~472):**

SZUKAJ:
```python
        scan_is_mocked = (
            callable(scan_cb)
            and getattr(scan_cb, "__module__", "").startswith("unittest.mock")
        )

        if not (verify_is_real_method and scan_is_mocked):
```
ZASTĄP:
```python
        if verify_is_real_method:
```
Sprawdź co znajduje się w bloku `if not (verify_is_real_method and scan_is_mocked):` —
zachowaj jego treść, zmień tylko warunek na `if verify_is_real_method:`.

**Zmiana 3 — isinstance Mock check (linia ~1002):**

SZUKAJ:
```python
                if isinstance(self.hass, Mock):
                    module = await _load_scanner_module(self.hass)
                    cap_cls = DeviceCapabilities or module.DeviceCapabilities
                    data, options = self._prepare_entry_payload(cap_cls)
                    return self.async_create_entry(
                        title=str(
                            self._device_info.get(
                                "device_name", self._data.get(CONF_NAME, DEFAULT_NAME)
                            )
```
Znajdź cały blok `if isinstance(self.hass, Mock): ... else: ...` i usuń gałąź `if`,
zostawiając tylko treść gałęzi `else` (lub kontynuację normalnego flow po bloku).

> Po tych zmianach uruchom cały suite testów. Jeśli testy zakładają Mock-detection
> i failują — zaktualizuj testy żeby nie wymagały tej logiki w produkcji.

---

## BLOK 8 — Usuń nieużywane deklaracje global

### `entity_mappings.py` (linia ~1739–1742)

SZUKAJ:
```python
    global NUMBER_ENTITY_MAPPINGS, BINARY_SENSOR_ENTITY_MAPPINGS
    global SWITCH_ENTITY_MAPPINGS, SELECT_ENTITY_MAPPINGS, TIME_ENTITY_MAPPINGS
    global TEXT_ENTITY_MAPPINGS, ENTITY_MAPPINGS
```
ZASTĄP:
```python
    global NUMBER_ENTITY_MAPPINGS, TIME_ENTITY_MAPPINGS, ENTITY_MAPPINGS
```
Uwaga: `BINARY_SENSOR_ENTITY_MAPPINGS`, `SWITCH_ENTITY_MAPPINGS`, `SELECT_ENTITY_MAPPINGS`,
`TEXT_ENTITY_MAPPINGS` są modyfikowane przez `.update()` — nie wymagają `global`
bo `.update()` mutuje obiekt bez przypisania. Zostaw `global` tylko dla tych
które są bezpośrednio przypisywane (`=`).

### `const.py` — `async_setup_options` (linia ~387–389)

Funkcja używa `globals()[name] = value` zamiast bezpośredniego przypisania,
dlatego pyflakes zgłasza `global X is unused`. To właściwie bug w podejściu —
`global` + `globals()` jest zbędne. Napraw w dwóch krokach:

SZUKAJ (w `async_setup_options`):
```python
    global SPECIAL_MODE_OPTIONS, DAYS_OF_WEEK, PERIODS, BYPASS_MODES, GWC_MODES
    global FILTER_TYPES, RESET_TYPES, MODBUS_PORTS, MODBUS_BAUD_RATES
    global MODBUS_PARITY, MODBUS_STOP_BITS

    filenames = [
        ("special_modes.json", "SPECIAL_MODE_OPTIONS"),
        ...
    ]
    ...
    for (_, name), value in zip(filenames, results, strict=False):
        globals()[name] = value
```
ZASTĄP (przypisania bezpośrednie zamiast globals()):
```python
    global SPECIAL_MODE_OPTIONS, DAYS_OF_WEEK, PERIODS, BYPASS_MODES, GWC_MODES
    global FILTER_TYPES, RESET_TYPES, MODBUS_PORTS, MODBUS_BAUD_RATES
    global MODBUS_PARITY, MODBUS_STOP_BITS

    filenames = [
        ("special_modes.json", "SPECIAL_MODE_OPTIONS"),
        ("days_of_week.json", "DAYS_OF_WEEK"),
        ("periods.json", "PERIODS"),
        ("bypass_modes.json", "BYPASS_MODES"),
        ("gwc_modes.json", "GWC_MODES"),
        ("filter_types.json", "FILTER_TYPES"),
        ("reset_types.json", "RESET_TYPES"),
        ("modbus_ports.json", "MODBUS_PORTS"),
        ("modbus_baud_rates.json", "MODBUS_BAUD_RATES"),
        ("modbus_parity.json", "MODBUS_PARITY"),
        ("modbus_stop_bits.json", "MODBUS_STOP_BITS"),
    ]

    if hass is not None:
        results = await asyncio.gather(
            *[hass.async_add_executor_job(_load_json_option, fn) for fn, _ in filenames]
        )
    else:
        results = [_load_json_option(fn) for fn, _ in filenames]

    (
        SPECIAL_MODE_OPTIONS, DAYS_OF_WEEK, PERIODS, BYPASS_MODES, GWC_MODES,
        FILTER_TYPES, RESET_TYPES, MODBUS_PORTS, MODBUS_BAUD_RATES,
        MODBUS_PARITY, MODBUS_STOP_BITS,
    ) = results
```

---

## BLOK 9 — Napraw redefinicję datetime w services.py

### `services.py` (linia ~21–35)

Pyflakes: `redefinition of unused 'datetime' from line 7`.
Powód: `from datetime import datetime` na linii 7, potem w fallback bloku
lokalna zmienna też nazywa się `datetime`.

SZUKAJ w fallback bloku (wewnątrz `except (ModuleNotFoundError, ImportError):`):
```python
    from datetime import datetime

    class _DTUtil:
        """Fallback minimal dt util."""

        @staticmethod
        def now() -> datetime:
            return datetime.now()

        @staticmethod
        def utcnow() -> datetime:
            utc = datetime.UTC if hasattr(datetime, "UTC") else timezone.utc  # noqa: UP017
            return datetime.now(utc)
```
ZASTĄP:
```python
    import datetime as _datetime_module

    class _DTUtil:
        """Fallback minimal dt util."""

        @staticmethod
        def now() -> _datetime_module.datetime:
            return _datetime_module.datetime.now()

        @staticmethod
        def utcnow() -> _datetime_module.datetime:
            utc = _datetime_module.datetime.UTC if hasattr(_datetime_module.datetime, "UTC") else timezone.utc
            return _datetime_module.datetime.now(utc)
```

---

## BLOK 10 — async_step_reconfigure w ConfigFlow

### `config_flow.py` — w klasie `ConfigFlow` (po linii 577)

Dodaj metodę po `def __init__`:

```python
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow user to update host/port/slave_id without removing the entry."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SLAVE_ID: user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=entry.data.get(CONF_HOST, ""),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Required(
                        CONF_SLAVE_ID,
                        default=entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                }
            ),
        )
```

### `strings.json` — dodaj sekcję reconfigure

Znajdź sekcję `"config"` → `"step"` i dodaj po ostatnim kroku:

```json
      "reconfigure": {
        "title": "Reconfigure ThesslaGreen",
        "description": "Update the connection settings for your AirPack device.",
        "data": {
          "host": "IP Address",
          "port": "Port",
          "slave_id": "Modbus Slave ID"
        }
      }
```

### `translations/pl.json` — dodaj sekcję reconfigure

```json
      "reconfigure": {
        "title": "Zmień konfigurację ThesslaGreen",
        "description": "Zaktualizuj ustawienia połączenia z rekuperatorem AirPack.",
        "data": {
          "host": "Adres IP",
          "port": "Port",
          "slave_id": "Adres Modbus (Slave ID)"
        }
      }
```

---

## BLOK 11 — DHCP i Zeroconf discovery handlery

### `config_flow.py`

Dodaj importy na górze pliku (przy innych importach z homeassistant):

```python
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.zeroconf import ZeroconfServiceInfo
```

W klasie `ConfigFlow` dodaj atrybut instancji w `__init__`:

SZUKAJ:
```python
    def __init__(self) -> None:
        """Initialize config flow."""
```
ZASTĄP:
```python
    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered_host: str | None = None
```

Dodaj metody w klasie `ConfigFlow` (przed `async_step_user`):

```python
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery of AirPack device."""
        await self.async_set_unique_id(discovery_info.macaddress.upper())
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info.ip}
        )
        self._discovered_host = discovery_info.ip
        return await self.async_step_user()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery of AirPack device."""
        await self.async_set_unique_id(discovery_info.host)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info.host}
        )
        self._discovered_host = discovery_info.host
        return await self.async_step_user()
```

W `async_step_user` użyj `self._discovered_host` jako defaultu dla pola host.
Znajdź gdzie budowany jest schema dla pola CONF_HOST i dodaj:

```python
vol.Required(
    CONF_HOST,
    default=self._discovered_host or vol.UNDEFINED,
): str,
```

---

## Weryfikacja po wszystkich blokach

```bash
# Uruchom pełne testy
cd tests && python -m pytest -x -q 2>&1 | tail -30

# Sprawdź brak ostrzeżeń pyflakes
cd custom_components && python -m pyflakes thessla_green_modbus/ 2>&1

# Sprawdź że nie ma już hass.data[DOMAIN] odczytów
grep -rn "hass\.data\[DOMAIN\]\[" custom_components/thessla_green_modbus/ 2>&1

# Sprawdź że nie ma FlowResult
grep -rn "from homeassistant.data_entry_flow import FlowResult" custom_components/thessla_green_modbus/ 2>&1

# Sprawdź że nie ma unittest.mock w produkcji
grep -rn "from unittest.mock" custom_components/thessla_green_modbus/ 2>&1

# Sprawdź że nie ma literówki
grep -rn "antifreez_stage" custom_components/thessla_green_modbus/ 2>&1

# Sprawdź że MAX_REGISTERS jest zaktualizowane
grep -n "MAX_REGISTERS_PER_REQUEST = " custom_components/thessla_green_modbus/const.py 2>&1
```

Oczekiwane wyniki:
- testy: wszystkie zielone
- pyflakes: brak nowych ostrzeżeń (porównaj z listą przed zmianami)
- hass.data[DOMAIN][ grep: brak wyników
- FlowResult grep: brak wyników
- unittest.mock grep: brak wyników
- antifreez_stage grep: brak wyników
- MAX_REGISTERS: `MAX_REGISTERS_PER_REQUEST = 60`

---

## Co NIE wymaga zmian

Następujące fragmenty są poprawne — nie ruszaj:

- `group_reads()` w `modbus_helpers.py` — poprawny algorytm batching
- `_crc16()` / `_append_crc()` w `modbus_transport.py` — poprawna implementacja CRC
- `device_name` dekoder w `scanner_core.py` linia 1137–1149 — już poprawnie czyta 8 rejestrów
- Logika backoff/jitter w `modbus_helpers.py` — poprawna implementacja
- `BaseModbusTransport` ABC — dobra architektura, nie zmieniaj interfejsu
- `FramerType` kompatybilność w `modbus_helpers.py` — poprawne fallbacki
- `slave`/`unit`/`device_id` introspection w `_call_modbus` — poprawna obsługa API pymodbus
- 96 plików testów w `tests/` — nie modyfikuj testów w ramach tych zadań
  (chyba że blok 7 wymusza dostosowanie konkretnego testu)
