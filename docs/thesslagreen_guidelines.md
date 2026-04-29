# ThesslaGreen Modbus — Wytyczne implementacyjne dla Codexa

## Cel

Ten dokument definiuje zasady pracy przy refaktoryzacji integracji:

```text
custom_components/thessla_green_modbus
```

Celem nie jest mechaniczne zmniejszenie liczby plików, tylko uporządkowanie architektury według odpowiedzialności.

Docelowy kierunek:

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

---

## Zasady nadrzędne

```text
1. Home Assistant ma być cienką warstwą.
2. Logika urządzenia ma być poza HA.
3. Modbus I/O ma być wyłącznie w transport/core.
4. Rejestry mają być opisane w jednym źródle prawdy.
5. Testy mają potwierdzać zachowanie, nie tylko pokrycie linii.
6. Refaktoryzacja nie może zostawiać legacy/shimów.
```

---

## Twarde reguły

```text
1. core/, transport/, registers/ i scanner/ nie mogą importować Home Assistant.
2. coordinator/ nie wykonuje bezpośrednio Modbus I/O.
3. Platformy HA nie dekodują raw register values.
4. transport/ nie zna nazw rejestrów ThesslaGreen.
5. registers/ nie wykonuje I/O.
6. scanner/ nie zna HA.
7. mappings/ może importować HA, bo jest warstwą mapowania encji.
8. Testy platformowe używają real HA/PHCC, bez platform_stubs.py.
9. Testy mają opisywać zachowanie, nie pokrycie linii.
10. Nie optymalizować pod liczbę plików, tylko pod odpowiedzialność modułów.
11. Nie tworzyć legacy modules, compatibility shims ani re-export shimów.
12. Po przepisaniu kodu na nową warstwę usunąć stary odpowiednik.
13. migracja do pakietu coordinator/ została wykonana i jest stanem bieżącym.
14. nie odtwarzamy top-level `coordinator.py`; importy kierujemy do modułów kanonicznych.
```

---


## Stan przejściowy (aktualny)

Stan bieżący po migracji coordinatora:

```text
- katalog coordinator/ jest aktywną lokalizacją kanoniczną,
- top-level coordinator.py nie istnieje,
- nie tworzymy shimów ani proxy modułów,
- nie dokumentujemy migracji, jeśli nie ma realnego kodu migracyjnego.
```

Migracja `coordinator.py` -> `coordinator/` została zakończona w dedykowanym PR. Importy aktualizujemy bezpośrednio (bez compatibility/re-export/proxy shimów).

---

## Co wolno robić

Codex może:

```text
- przenosić kod między warstwami zgodnie z architekturą,
- aktualizować importy po przeniesieniu kodu,
- usuwać stare moduły po przeniesieniu funkcji,
- scalać mikropliki, jeśli tworzą jedną odpowiedzialność,
- wydzielać duże moduły, jeśli zawierają różne odpowiedzialności,
- poprawiać typing,
- poprawiać nazwy funkcji i klas, jeśli zwiększa to czytelność,
- dopisywać behavioral tests,
- usuwać testy coverage-driven po przeniesieniu wartościowych scenariuszy,
- upraszczać conftest.py po usunięciu platform stubs,
- aktualizować dokumentację techniczną.
```

---

## Czego nie wolno robić

Codex nie może:

```text
- usuwać funkcjonalności bez testu lub uzasadnienia,
- zmieniać znaczenia rejestrów,
- zmieniać adresów rejestrów bez walidacji,
- duplikować definicji rejestrów poza JSON + loader/schema,
- zmieniać publicznych service schemas bez testów i dokumentacji,
- dodawać importów HA do core/transport/registers/scanner,
- wykonywać Modbus I/O w coordinator/platformach,
- dekodować raw register values w platformach,
- zostawiać martwych shimów,
- tworzyć plików *_legacy.py lub *_compat.py,
- tworzyć proxy/re-export modules tylko dla starych importów,
- robić wielkich PR-ów bez etapów,
- zastępować real HA testów stubami,
- pisać testów wyłącznie dla coverage,
- ignorować ruff/mypy/pytest.
```

---

## Zakazane zależności

Zakazane importy:

```text
core/       -> homeassistant
transport/  -> homeassistant
registers/  -> homeassistant
scanner/    -> homeassistant
transport/  -> mappings/platformy/encje
registers/  -> transport I/O
platformy   -> transport/pymodbus/raw registers
```

Dopuszczalne:

```text
HA Layer      -> Coordinator
Coordinator   -> Core
Core          -> Registers / Scanner / Transport
Scanner       -> Registers / Transport
Mappings      -> HA classes
```

---

## Brak legacy i shimów

Refaktoryzacja ma oznaczać przepisanie kodu do nowej struktury, a nie zachowanie starej struktury jako warstwy kompatybilności.

Zakazane są:

```text
- legacy modules,
- compatibility shims,
- re-export shims,
- proxy modules,
- pliki typu *_legacy.py,
- pliki typu *_compat.py,
- adaptery zachowujące starą strukturę importów,
- stare odpowiedniki funkcji pozostawione obok nowych,
- tymczasowe moduły bez realnej odpowiedzialności.
```

Obowiązkowy proces przenoszenia kodu:

```text
1. Przenieś funkcję/klasę do docelowej warstwy.
2. Zaktualizuj wszystkie importy.
3. Przenieś lub popraw testy.
4. Usuń stary moduł/funkcję.
5. Uruchom testy dla dotkniętego obszaru.
6. Nie zostawiaj shimów.
```

Wyjątek:

```text
Shim może zostać tylko wtedy, gdy wymaga tego Home Assistant public API albo realna migracja użytkowników.
Taki wyjątek musi mieć komentarz w kodzie, test oraz wpis w dokumentacji.
```

---

## Docelowa struktura katalogów

```text
custom_components/thessla_green_modbus/
├── __init__.py
├── manifest.json
├── strings.json
├── services.yaml
├── const.py
├── entity.py
├── diagnostics.py
├── repairs.py
├── sensor.py
├── binary_sensor.py
├── switch.py
├── number.py
├── select.py
├── text.py
├── time.py
├── fan.py
├── climate.py
├── coordinator/
├── core/
├── transport/
├── registers/
├── scanner/
├── mappings/
├── services.py
├── services_schema.py
├── services_helpers.py
├── services_targets.py
├── services_handlers.py
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

## Odpowiedzialność warstw

### HA Layer

```text
__init__.py
config_flow.py
services.py
diagnostics.py
repairs.py
entity.py
platformy HA
mappings/
```

Odpowiedzialność:

```text
- lifecycle HA,
- encje,
- config flow,
- options flow,
- reauth,
- usługi,
- diagnostyka,
- repairs,
- mapowanie danych na encje.
```

---

### coordinator/

Odpowiedzialność:

```text
- DataUpdateCoordinator,
- update cycle,
- unavailable/offline state,
- statystyki,
- scan cache w config entry,
- delegacja do core/client.py.
```

Zakazane:

```text
- direct Modbus I/O,
- raw register decoding,
- bezpośrednie użycie pymodbus,
- scanner-specific I/O.
```

---

### core/

Odpowiedzialność:

```text
- ThesslaGreenClient,
- DeviceSnapshot,
- DeviceIdentity,
- PollStatistics,
- błędy domenowe,
- orkiestracja read/write/scan.
```

Zakazane:

```text
- import Home Assistant,
- encje HA,
- config entry,
- repairs/diagnostics HA.
```

---

### transport/

Odpowiedzialność:

```text
- Modbus TCP,
- Modbus RTU,
- RTU-over-TCP,
- raw responses,
- retry/backoff,
- klasyfikacja błędów transportu.
```

Zakazane:

```text
- Home Assistant,
- nazwy rejestrów ThesslaGreen,
- encje,
- DeviceSnapshot.
```

---

### registers/

Odpowiedzialność:

```text
- RegisterDef,
- schema,
- loader,
- codec,
- ReadPlanner,
- JSON register definitions.
```

Zakazane:

```text
- I/O,
- Home Assistant,
- pymodbus client,
- encje HA.
```

---

### scanner/

Odpowiedzialność:

```text
- wykrywanie modelu,
- wykrywanie firmware,
- capabilities,
- safe/normal/deep scan,
- unsupported registers,
- scan runtime state.
```

Zakazane:

```text
- Home Assistant,
- encje HA,
- config entry updates,
- diagnostics HA.
```

---

### mappings/

Odpowiedzialność:

```text
- mapowanie rejestrów na encje HA,
- entity descriptions,
- device_class,
- state_class,
- entity_category,
- platform-specific mapping data.
```

Dozwolone:

```text
- import klas Home Assistant potrzebnych do opisów encji.
```

Zakazane:

```text
- Modbus I/O,
- raw decoding,
- scanner logic.
```

---

## Reguły testów

### Zakazane

```text
- platform_stubs.py,
- install_climate_stubs(),
- install_fan_stubs(),
- install_sensor_stubs(),
- patchowanie sys.modules dla Home Assistant,
- testy coverage-driven,
- assert result is not None bez znaczenia biznesowego.
```

### Wymagane

```text
- testy opisujące zachowanie,
- real HA/PHCC dla platform i config flow,
- mock transport/pymodbus dla warstw niższych,
- pure unit tests dla registers/codec/read_planner/errors.
```

---

## Test tiers

### Tier 1 — pure unit

Bez HA, bez pymodbus, bez sieci.

Zakres:

```text
registers
codec
read_planner
retry
errors
const
```

---

### Tier 2 — mock I/O

Zakres:

```text
transport
scanner
core/client
coordinator z mock clientem
service handlers
```

---

### Tier 3 — real HA

Zakres:

```text
setup/unload/reload
config flow
options flow
reauth
platformy
diagnostics
services
entity unique_id
unavailable state
```

---

## Dobre nazwy testów

Przykłady:

```python
test_marks_entities_unavailable_when_device_times_out()
test_reuses_scan_cache_when_device_scan_is_disabled()
test_skips_unsupported_register_after_illegal_address()
test_raises_service_validation_error_for_unknown_register()
test_creates_only_supported_entities_after_scan()
```

---

## Reguły rozmiaru plików

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

## Definition of Done dla PR

Każdy PR musi spełniać:

```text
- ruff = green,
- pytest dla dotkniętego tieru = green,
- mypy = green, jeśli projekt używa mypy,
- brak nowych importów HA w core/transport/registers/scanner,
- brak direct Modbus I/O w coordinator/platformach,
- brak raw register decoding w platformach,
- brak martwych plików po refaktoryzacji,
- brak nowych legacy/compat/proxy modules,
- brak generic helpers.py/utils2.py/misc.py bez jasnej odpowiedzialności,
- brak testów typu assert result is not None bez znaczenia biznesowego,
- zachowana kompatybilność funkcjonalna,
- README/docs linkują tylko do istniejących plików, jeśli PR dotyka dokumentacji.
```

---

## Kolejność prac

```text
1. Foundation testów: PHCC, markery, komendy.
2. Platform tests na real HA.
3. Usunięcie platform_stubs.py i uproszczenie conftest.py.
4. core/errors + transport/retry.
5. split registers.
6. transport package.
7. core/client + delegacja z coordinatora.
8. scanner cleanup.
9. services cleanup.
10. config flow cleanup.
11. coordinator cleanup.
12. cleanup coverage-driven tests.
```

Nie zaczynać od dużej przebudowy coordinatora, dopóki testy HA/platform nie są stabilne.

---

## Finalna zasada

Przy każdej zmianie pytaj:

```text
Czy ten plik ma jedną odpowiedzialność?
Czy ta warstwa ma poprawne zależności?
Czy da się to łatwo przetestować?
Czy po refaktoryzacji usunięto stary odpowiednik?
Czy zmiana przybliża integrację do stabilnego HA Silver/Gold?
```
