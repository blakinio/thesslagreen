# Codex Guidelines — ThesslaGreen Modbus Refactor

## Cel dokumentu
Ten dokument opisuje zasady pracy dla Codexa przy refaktoryzacji integracji:

```text
custom_components/thessla_green_modbus
```

Celem nie jest mechaniczne zmniejszenie liczby plików, tylko uporządkowanie architektury według odpowiedzialności:

```text
Home Assistant platformy
        ↓
ThesslaGreenCoordinator
        ↓
ThesslaGreenClient / core
        ↓
ReadPlanner + RegisterCodec + Scanner
        ↓
Transport TCP / RTU / RTU-over-TCP
        ↓
pymodbus / raw socket
```

Najważniejsze założenie:

```text
Home Assistant ma być cienką warstwą.
Logika urządzenia, Modbus, rejestry, scanner i codec mają być poza HA.
Coordinator ma koordynować lifecycle HA, a nie wykonywać niskopoziomową logikę Modbus.
```

---

## 1. Zasady nadrzędne

### 1.1 Co jest celem
Codex ma dążyć do:

```text
- czytelnej architektury warstwowej,
- jasnych granic odpowiedzialności,
- mniejszej liczby mikrohelperów,
- braku dużych monolitów,
- testów zachowania zamiast testów coverage-driven,
- zgodności z Home Assistant lifecycle,
- przygotowania integracji pod jakość Silver/Gold,
- zachowania kompatybilności funkcjonalnej.
```

### 1.2 Co nie jest celem
Codex NIE ma optymalizować pod samą liczbę plików.
Nie robić zmian typu:

```text
111 plików -> 50 plików za wszelką cenę
```

Właściwy cel:

```text
każdy moduł ma jasną odpowiedzialność,
wiadomo jak go testować,
wiadomo jakie ma zależności,
wiadomo czego NIE powinien robić.
```

---

## 2. Twarde reguły architektury

### 2.1 Zakazane zależności
Poniższe katalogi NIE mogą importować Home Assistant:

```text
core/
transport/
registers/
scanner/
```

Zakazane importy w tych katalogach:

```python
from homeassistant...
import homeassistant
```

Wyjątek: brak.
Jeśli kod potrzebuje typu lub funkcji z HA, oznacza to, że znajduje się w złej warstwie.

### 2.2 Coordinator nie wykonuje bezpośrednio Modbusa
`coordinator/` NIE powinien bezpośrednio wołać:

```text
read_holding_registers()
read_input_registers()
read_coils()
write_register()
pymodbus client methods
raw socket calls
```

Coordinator powinien delegować do:

```python
ThesslaGreenClient.read_snapshot()
ThesslaGreenClient.write_register()
ThesslaGreenClient.scan_capabilities()
```

Dopuszczalne w `coordinator/`:

```text
- DataUpdateCoordinator lifecycle,
- setup/shutdown,
- HA unavailable/offline state,
- statystyki update,
- scan cache w ConfigEntry options,
- diagnostics-facing status,
- update listener,
- delegacja do core/client.py.
```

Niedopuszczalne w `coordinator/`:

```text
- raw Modbus operations,
- register decoding,
- register grouping,
- pymodbus-specific retry,
- scanner I/O,
- direct register map mutation bez warstwy core/registers.
```

### 2.3 Platformy HA nie dekodują rejestrów
Pliki:

```text
sensor.py
binary_sensor.py
switch.py
number.py
select.py
text.py
time.py
fan.py
climate.py
```

Nie powinny dekodować raw register values.
Platformy powinny czytać gotowe dane z:

```python
coordinator.data
DeviceSnapshot
```

Dopuszczalne:

```text
- formatowanie wartości dla HA,
- entity descriptions,
- device_class / state_class / entity_category,
- wywołanie service/write przez client/coordinator,
- availability,
- unique_id,
- device_info.
```

Niedopuszczalne:

```text
- multiplier/resolution decode,
- BCD decode,
- enum decode z raw register values,
- bezpośrednie Modbus reads/writes,
- skanowanie możliwości urządzenia.
```

### 2.4 Transport nie zna ThesslaGreen
`transport/` zna tylko Modbus.
Nie wolno tam używać:

```text
- nazw rejestrów ThesslaGreen,
- DeviceCapabilities,
- EntitySpec,
- Home Assistant,
- DeviceSnapshot.
```

Transport może znać:

```text
- address,
- count,
- function code,
- unit/slave id,
- timeout,
- retry/backoff,
- raw Modbus response,
- raw Modbus exception.
```

### 2.5 Registers nie wykonuje I/O
`registers/` odpowiada tylko za:

```text
- definicje rejestrów,
- walidację JSON,
- cache definicji,
- encode/decode,
- read plan,
- mapowanie nazwa -> definicja.
```

Nie wolno tam:

```text
- otwierać połączenia,
- czytać z urządzenia,
- pisać do urządzenia,
- importować HA,
- importować pymodbus clienta.
```

### 2.6 Scanner nie zna HA
`scanner/` może używać:

```text
- transport/,
- registers/,
- core/errors.py.
```

`scanner/` nie może używać:

```text
- Home Assistant,
- ConfigEntry,
- DataUpdateCoordinator,
- HA diagnostics,
- HA repairs,
- HA entity classes.
```

### 2.7 Mappings to warstwa HA mapping
`mappings/` może importować klasy HA typu:

```python
SensorDeviceClass
SensorStateClass
EntityCategory
BinarySensorDeviceClass
```

To jest dozwolone, ponieważ `mappings/` jest warstwą mapowania encji HA, a nie czystym core.

---

## 3. Docelowa struktura produkcyjna

```text
custom_components/thessla_green_modbus/
│
├── manifest.json
├── strings.json
├── services.yaml
├── options/
│
│  ── HA ENTRY / LIFECYCLE ─────────────────────────
├── __init__.py
├── const.py
├── entity.py
├── diagnostics.py
├── repairs.py
│
│  ── PLATFORMY HA ─────────────────────────────────
├── sensor.py
├── binary_sensor.py
├── switch.py
├── number.py
├── select.py
├── text.py
├── time.py
├── fan.py
├── climate.py
│
│  ── COORDINATOR — HA ADAPTER ─────────────────────
├── coordinator/
│   ├── __init__.py
│   ├── coordinator.py
│   ├── models.py
│   ├── lifecycle.py
│   ├── update.py
│   ├── scan.py
│   ├── capabilities.py
│   └── schedule.py
│
│  ── CORE — LOGIKA URZĄDZENIA, BEZ HA ─────────────
├── core/
│   ├── __init__.py
│   ├── client.py
│   ├── snapshot.py
│   ├── config.py
│   └── errors.py
│
│  ── TRANSPORT — KOMUNIKACJA MODBUS, BEZ HA ───────
├── transport/
│   ├── __init__.py
│   ├── base.py
│   ├── factory.py
│   ├── tcp.py
│   ├── rtu.py
│   ├── rtu_over_tcp.py
│   ├── retry.py
│   └── crc.py
│
│  ── REJESTRY — PROTOKÓŁ THESSLAGREEN, BEZ HA ────
├── registers/
│   ├── __init__.py
│   ├── thessla_green_registers_full.json
│   ├── definition.py
│   ├── loader.py
│   ├── schema.py
│   ├── codec.py
│   ├── read_planner.py
│   └── reference.py
│
│  ── SCANNER — WYKRYWANIE URZĄDZENIA, BEZ HA ─────
├── scanner/
│   ├── __init__.py
│   ├── core.py
│   ├── orchestration.py
│   ├── capabilities.py
│   ├── firmware.py
│   ├── selection.py
│   ├── registers.py
│   ├── io.py
│   └── state.py
│
│  ── MAPOWANIA ENCJI — WARSTWA HA MAPPING ─────────
├── mappings/
│   ├── __init__.py
│   ├── _loaders.py
│   ├── _helpers.py
│   ├── _static_sensors.py
│   ├── _static_discrete.py
│   ├── _static_numbers.py
│   └── special_modes.py
│
│  ── SERWISY HA ───────────────────────────────────
├── services.py
├── services_schema.py
├── services_helpers.py
├── services_targets.py
├── services_handlers.py
│
│  ── CONFIG FLOW ──────────────────────────────────
├── config_flow.py
├── config_flow_schema.py
├── config_flow_options.py
├── config_flow_options_form.py
├── config_flow_entry.py
├── config_flow_payloads.py
├── config_flow_runtime.py
├── config_flow_validation.py
└── config_flow_steps.py
```

---

## 4. Odpowiedzialność modułów produkcyjnych

### 4.1 `__init__.py`
Dozwolone:

```text
- async_setup_entry
- async_unload_entry
- async_migrate_entry
- async_update_options
- setup coordinator
- setup/unload platforms
- setup/unload services
```

Zakazane:

```text
- Modbus read/write,
- register decode,
- scanner logic,
- business logic urządzenia.
```

### 4.2 `const.py`
Dozwolone:

```text
- DOMAIN,
- CONF_*,
- DEFAULT_*,
- platform list,
- proste stałe.
```

Zakazane:

```text
- klasy,
- logika,
- register metadata,
- capabilities rules,
- entity mapping data.
```

### 4.3 `core/client.py`
Główna klasa domenowa.
Powinno zawierać:

```python
class ThesslaGreenClient:
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def read_snapshot(self) -> DeviceSnapshot: ...
    async def write_register(self, name: str, value: object) -> None: ...
    async def scan_capabilities(self) -> DeviceCapabilities: ...
```

Tu jest realna orkiestracja:

```text
transport + registers/read_planner + registers/codec + scanner
```

### 4.4 `core/snapshot.py`
Powinno zawierać:

```text
- DeviceSnapshot
- DeviceIdentity
- RuntimeStatus
- PollStatistics
```

`DeviceSnapshot` jest jedynym źródłem danych dla encji HA.

### 4.5 `core/errors.py`
Powinno zawierać domenowe błędy integracji:

```text
- ThesslaGreenError
- CannotConnect
- InvalidAuth
- ThesslaGreenConfigError
- ThesslaGreenProtocolError
- UnsupportedRegisterError
- TransportUnavailableError
```

### 4.6 `transport/base.py`
Powinno zawierać:

```python
class ModbusTransport(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def read_holding_registers(self, address: int, count: int) -> RawModbusResponse: ...
    async def read_input_registers(self, address: int, count: int) -> RawModbusResponse: ...
    async def read_coils(self, address: int, count: int) -> RawModbusResponse: ...
    async def write_register(self, address: int, value: int) -> RawModbusWriteResponse: ...
```

### 4.7 `transport/factory.py`
Powinno zawierać:

```text
- create_transport(config)
- wybór TCP / RTU / RTU-over-TCP
- auto-detection, jeśli konieczne
```

### 4.8 `transport/retry.py`
Powinno zawierać:

```python
class ErrorKind(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNSUPPORTED_REGISTER = "unsupported_register"
    TIMEOUT = "timeout"
    PROTOCOL = "protocol"
    CONFIGURATION = "configuration"
```

Oraz:

```text
- RetryDecision
- classify_transport_error()
- should_retry()
- calculate_backoff()
```

### 4.9 `registers/definition.py`
Powinno zawierać:

```text
- RegisterDef
- RegisterFunction
- ReadBlock
- ReadPlan
```

### 4.10 `registers/loader.py`
Powinno zawierać:

```text
- load_registers()
- async_load_registers()
- cache JSON
- hash / mtime
- get_register_by_name()
```

### 4.11 `registers/codec.py`
Powinno zawierać:

```text
- decode_value()
- encode_value()
- enum handling
- multiplier / resolution
- BCD time
- invalid values, np. 32768 -> None/unknown
```

### 4.12 `registers/read_planner.py`
Powinno zawierać:

```text
- ReadPlanner
- grupowanie rejestrów w batch-e
- limit 16 registers/request
- omijanie dziur adresowych
- uwzględnianie capabilities
```

### 4.13 `scanner/`
Scanner odpowiada za wykrywanie urządzenia i capabilities.
Dozwolone:

```text
- safe scan,
- normal scan,
- deep scan,
- firmware detection,
- model detection,
- available/unsupported register detection,
- capability rules.
```

Zakazane:

```text
- import Home Assistant,
- tworzenie encji,
- diagnostics HA,
- repairs HA,
- config entry updates.
```

### 4.14 `coordinator/`
Coordinator jest adapterem HA.
Dozwolone:

```text
- DataUpdateCoordinator,
- update cycle,
- unavailable/offline state,
- statystyki,
- scan cache w ConfigEntry,
- delegowanie do core/client.py.
```

Zakazane:

```text
- bezpośredni Modbus read/write,
- raw register decode,
- pymodbus-specific code,
- scanner-specific I/O.
```

### 4.15 `mappings/`
Dozwolone:

```text
- mapowanie rejestrów na encje,
- EntityCategory,
- SensorDeviceClass,
- SensorStateClass,
- platform-specific descriptions.
```

Zakazane:

```text
- Modbus I/O,
- raw decoding,
- scanner logic.
```

### 4.16 `services_handlers.py`
Dozwolone:

```text
- handler logic,
- walidacja payloadu,
- delegowanie do coordinator/client,
- request refresh po zapisie.
```

Sekcje obowiązkowe:

```text
DATA
MODE
PARAMETERS
MAINTENANCE
SCHEDULE
```

Jeżeli plik przekroczy 700–800 linii, rozważyć rozbicie na:

```text
services/
  handlers.py
  mode.py
  parameters.py
  maintenance.py
  schedule.py
```

---

## 5. Docelowa struktura testów

```text
tests/
│
├── conftest.py
│
├── unit/
│   ├── test_register_schema.py
│   ├── test_register_definition.py
│   ├── test_register_uniqueness.py
│   ├── test_register_codec.py
│   ├── test_read_planner.py
│   ├── test_register_loader.py
│   ├── test_registers_vs_reference.py
│   ├── test_transport_retry.py
│   ├── test_errors.py
│   └── test_const.py
│
├── transport/
│   ├── test_tcp.py
│   ├── test_rtu.py
│   ├── test_rtu_over_tcp.py
│   ├── test_transport_factory.py
│   └── test_transport_errors.py
│
├── scanner/
│   ├── test_scanner_identity.py
│   ├── test_scanner_capabilities.py
│   ├── test_scanner_registers.py
│   ├── test_scanner_lifecycle.py
│   ├── test_scanner_errors.py
│   └── test_scanner_io.py
│
├── core/
│   ├── test_client_lifecycle.py
│   ├── test_client_read_snapshot.py
│   ├── test_client_write_register.py
│   ├── test_client_scan_capabilities.py
│   └── test_snapshot.py
│
├── coordinator/
│   ├── test_coordinator_setup.py
│   ├── test_coordinator_update.py
│   ├── test_coordinator_scan.py
│   ├── test_coordinator_capabilities.py
│   └── test_coordinator_lifecycle.py
│
├── ha/
│   ├── test_integration.py
│   ├── test_migration.py
│   ├── test_config_flow_user.py
│   ├── test_config_flow_options.py
│   ├── test_config_flow_reauth.py
│   ├── test_diagnostics.py
│   └── test_all_entity_creation.py
│
├── platforms/
│   ├── test_sensor.py
│   ├── test_binary_sensor.py
│   ├── test_switch.py
│   ├── test_number.py
│   ├── test_select.py
│   ├── test_text.py
│   ├── test_time.py
│   ├── test_fan.py
│   └── test_climate.py
│
└── services/
    ├── test_services.py
    ├── test_services_handlers.py
    └── test_services_scaling.py
```

---

## 6. Reguły testów

### 6.1 Zakaz platform stubs
Zakazane:

```text
platform_stubs.py
install_climate_stubs()
install_fan_stubs()
install_sensor_stubs()
sys.modules patching Home Assistant
```

Testy platform i HA mają używać real Home Assistant przez PHCC.

### 6.2 Testy mają testować zachowanie
Zakazane testy typu:

```python
assert result is not None
```

chyba że `None` ma znaczenie biznesowe.
Każdy test powinien odpowiadać na pytanie:

```text
co się dzieje, gdy X?
```

Dobre przykłady nazw:

```python
test_marks_entities_unavailable_when_device_times_out()
test_reuses_scan_cache_when_device_scan_is_disabled()
test_skips_unsupported_register_after_illegal_address()
test_raises_service_validation_error_for_unknown_register()
test_creates_only_supported_entities_after_scan()
```

### 6.3 Tier 1 — pure unit
Bez HA, bez pymodbus, bez sieci.
Zakres:

```text
- registers,
- codec,
- read planner,
- retry classification,
- errors,
- constants.
```

### 6.4 Tier 2 — mock transport / mock pymodbus
Zakres:

```text
- transport,
- scanner,
- core client,
- coordinator with mocked client,
- service handlers with mocked coordinator/client.
```

### 6.5 Tier 3 — real HA
Zakres:

```text
- setup/unload/reload,
- config flow,
- options flow,
- reauth flow,
- platforms,
- diagnostics,
- service registration,
- entity unique_id,
- unavailable state.
```

---

## 7. Reguły rozmiaru plików
Nie są twarde, ale obowiązują jako review gate:

```text
0–250 linii      idealnie
250–500 linii    OK
500–700 linii    tylko jeśli moduł jest bardzo spójny
700+ linii       wymaga uzasadnienia
1000+ linii      prawie zawsze do podziału
```

Nie tworzyć nowych plików typu:

```text
helpers.py
utils2.py
misc.py
_facade.py
_runtime_helpers.py
```

bez jasnej odpowiedzialności.

---

## 8. Co wolno robić
Codex może:

```text
- przenosić kod między modułami zgodnie z granicami warstw,
- usuwać shimy po przeniesieniu importów,
- scalać mikropliki, jeśli tworzą jedną odpowiedzialność,
- wydzielać duże moduły, jeśli zawierają różne odpowiedzialności,
- poprawiać importy,
- dopisywać testy zachowania,
- usuwać testy coverage-driven po przeniesieniu wartościowych scenariuszy,
- upraszczać conftest.py po usunięciu platform stubs,
- poprawiać typing,
- poprawiać nazwy funkcji/klas, jeśli ułatwia to architekturę,
- aktualizować dokumentację techniczną.
```

---

## 9. Czego nie wolno robić
Codex NIE może:

```text
- usuwać funkcjonalności bez testu lub uzasadnienia,
- zmieniać znaczenia rejestrów,
- zmieniać adresów rejestrów bez walidacji,
- zmieniać publicznych service schemas bez migracji/dokumentacji,
- dodawać importów HA do core/transport/registers/scanner,
- wykonywać Modbus I/O w coordinator/platformach,
- dekodować raw register values w platformach,
- zostawiać martwych shimów,
- robić wielkich PR-ów bez etapów,
- zastępować real HA testów stubami,
- pisać testów wyłącznie dla coverage,
- ignorować ruff/mypy/pytest.
```

---

## 10. Kolejność prac

### PR 1 — test foundation
Cel:

```text
- upewnić się, że PHCC działa w CI,
- dodać pytest markers,
- przygotować komendy dla test tiers.
```

### PR 2 — platform tests na real HA
Cel:

```text
- usunąć install_*_stubs(),
- przepisać platform tests na real HA,
- nie patchować sys.modules.
```

### PR 3 — usunięcie platform_stubs.py i uproszczenie conftest.py
Dopiero po PR 2.
Usunąć:

```text
platform_stubs.py
_HA_AVAILABLE fallback
ensure_ha_compat_symbols
types.ModuleType autouse patches
```

### PR 4 — core errors + transport retry
Cel:

```text
- przenieść domenowe błędy do core/errors.py,
- przenieść retry/classification do transport/retry.py,
- ujednolicić ErrorKind i RetryDecision.
```

### PR 5 — registers split
Cel:

```text
- RegisterDef -> registers/definition.py,
- codec -> registers/codec.py,
- ReadPlanner -> registers/read_planner.py,
- loader zostaje tylko loaderem.
```

### PR 6 — transport package
Cel:

```text
- transport/base.py,
- transport/factory.py,
- transport/tcp.py,
- transport/rtu.py,
- transport/rtu_over_tcp.py,
- transport/retry.py,
- transport/crc.py, jeśli potrzebne.
```

### PR 7 — core/client.py
Cel:

```text
- utworzyć ThesslaGreenClient,
- przenieść realną orkiestrację read/write/scan z coordinatora,
- coordinator zaczyna delegować do clienta.
```

### PR 8 — scanner cleanup
Cel:

```text
- usunąć shimy scanner_*.py,
- przenieść capability rules do scanner/capabilities.py,
- uporządkować scanner/state.py,
- scanner nie importuje HA.
```

### PR 9 — services cleanup
Cel:

```text
- uporządkować services_handlers.py,
- sekcje DATA / MODE / PARAMETERS / MAINTENANCE / SCHEDULE,
- handler logic testowana behavioral tests.
```

### PR 10 — config flow cleanup
Cel:

```text
- config_flow.py tylko klasy flow,
- config_flow_steps.py kroki,
- config_flow_validation.py walidacja i error mapping.
```

### PR 11 — coordinator package
Cel:

```text
- coordinator jako HA adapter,
- bez direct Modbus I/O,
- bez raw decoding,
- delegacja do core/client.py.
```

### PR 12 — cleanup coverage-driven tests
Cel:

```text
- usunąć test_coordinator_coverage.py po przeniesieniu wartościowych scenariuszy,
- usunąć test_scanner_coverage.py po przeniesieniu wartościowych scenariuszy,
- usunąć test_config_flow_helpers.py, jeśli jest tylko coverage-driven,
- scalić duplikaty register tests.
```

---

## 11. Checklist przed zakończeniem każdego PR
Każdy PR musi spełniać:

```text
- ruff: 0 errors
- mypy: 0 errors, jeśli projekt używa mypy
- pytest dla dotkniętego tieru przechodzi
- brak nowych importów HA w core/transport/registers/scanner
- brak direct Modbus I/O w coordinator/platformach
- brak nowych testów typu assert result is not None bez znaczenia biznesowego
- brak martwych shimów i nieużywanych importów
- zachowana kompatybilność config entry/options
- jeśli zmieniono service schema, dodano test i dokumentację
```

---

## 12. Checklist Silver/Gold

### Silver readiness

```text
- config entry unload zamyka transport,
- encje przechodzą na unavailable przy offline,
- offline logowany raz,
- recovery logowany raz,
- service actions rzucają HomeAssistantError / ServiceValidationError,
- parallel updates ustawione świadomie,
- testy config flow,
- testy unload/reload,
- runtime_data zamiast hass.data jako głównego storage,
- brak platform stubs.
```

### Gold readiness

```text
- diagnostics bez sekretów,
- repairs dla typowych problemów,
- reconfigure flow,
- discovery DHCP/zeroconf, jeśli działa wiarygodnie,
- entity_category dla config/diagnostic,
- disabled_by_default dla noisy encji,
- tłumaczenia encji, wyjątków i nazw,
- dokumentacja supported devices/functions/troubleshooting,
- pełne testy platform z real HA.
```

---

## 13. Finalna zasada dla Codexa
Nie pytaj:

```text
czy można zmniejszyć liczbę plików?
```

Pytaj:

```text
czy ten plik ma jedną odpowiedzialność?
czy ta warstwa ma poprawne zależności?
czy da się to łatwo przetestować?
czy zmiana zbliża integrację do HA Silver/Gold?
czy użytkownik końcowy dostaje stabilniejszą integrację?
```

---

## 14. Polityka migracji legacy (w tym rzeczy z PDF/reference)
Zasada domyślna:

```text
Nie przenosimy 1:1 kodu legacy tylko dlatego, że istnieje.
Przenosimy wyłącznie logikę, która ma wartość funkcjonalną i jest potwierdzona testami/scenariuszami.
```

### 14.1 Co przepisywać od nowa
Przepisywać od nowa (clean implementation), gdy:

```text
- kod legacy miesza warstwy (HA + Modbus + decode w jednym miejscu),
- kod jest oparty o "historyczne" obejścia bez testów,
- logika jest trudna do utrzymania lub ma niejasne zależności,
- implementacja wynika z ograniczeń dawnej struktury projektu.
```

### 14.2 Co zachować z legacy
Zachować (lub migrować z walidacją), gdy:

```text
- dotyczy to znaczenia rejestrów, adresacji i semantyki urządzenia,
- zachowanie jest widoczne dla użytkownika (services, encje, wartości),
- istnieją sprawdzone scenariusze i testy regresji,
- to krytyczny kontrakt kompatybilności.
```

### 14.3 Jak traktować PDF i źródła referencyjne

```text
- PDF/reference traktujemy jako źródło prawdy domenowej (co urządzenie oznacza),
  ale nie jako wzorzec architektury kodu.
- Implementację robimy według nowej architektury warstwowej.
- Każda różnica względem legacy/PDF musi być udokumentowana i pokryta testem.
```

### 14.4 Bramka akceptacji zmian legacy
Każda zmiana "przepisana od nowa" przechodzi, jeśli:

```text
- zachowana jest kompatybilność funkcjonalna,
- testy behavioral dla scenariuszy legacy przechodzą,
- brak regresji w config flow/services/encjach,
- nie naruszono granic warstw i twardych reguł zależności.
```

---

## 15. Decyzja docelowa: pełne odejście od legacy
Od tego etapu przyjmujemy twardą decyzję projektową:

```text
- usuwamy kod legacy etapami aż do pełnego wygaszenia,
- nowa architektura jest jedyną wspieraną ścieżką implementacji,
- nie przenosimy legacy helperów/facad/proxy "bo działało wcześniej".
```

Shimy migracyjne (także krótkotrwałe) są niedozwolone.

```text
- nie dodajemy warstw przejściowych typu shim/proxy/facade,
- po przeniesieniu funkcji usuwamy legacy kod w tym samym PR,
- jeśli potrzebna jest kompatybilność, realizujemy ją testami i jasnym API docelowym,
  a nie dodatkową warstwą pośrednią.
```

### 15.1 Jedno źródło prawdy dla rejestrów

```text
Plik registers/thessla_green_registers_full.json jest jedynym źródłem prawdy
(Single Source of Truth) dla definicji rejestrów.
```

Konsekwencje:

```text
- brak duplikowania definicji/adresów rejestrów w kodzie Python,
- brak "ręcznych" tabel register map poza loader/schema/definition,
- każda zmiana rejestru idzie przez JSON + walidację schema + testy.
```

### 15.2 Kontrakt migracyjny

```text
- przepisywanie funkcji realizujemy na nowo w warstwach docelowych,
- zachowanie użytkowe utrzymujemy przez testy behavioral,
- po przeniesieniu funkcji usuwamy legacy kod bez pozostawiania martwych kopii.
```
