# ThesslaGreen Modbus — Refactor Guidelines (Minimum Required)

## 1) Cel
Refaktor ma dać stabilną, testowalną architekturę warstwową — nie „redukcję liczby plików”.

## 2) Docelowy podział warstw
1. **HA layer**: `__init__.py`, platformy, config flow, services, diagnostics/repairs
2. **Coordinator (HA adapter)**: lifecycle + update cycle + delegacja
3. **Core**: logika domenowa urządzenia
4. **Registers**: definicje/codec/read planner (bez I/O)
5. **Scanner**: wykrywanie capabilities (bez HA)
6. **Transport**: Modbus TCP/RTU/RTU-over-TCP (bez wiedzy domenowej)

## 3) Twarde reguły zależności
### 3.1 Brak importów HA poza warstwą HA/mappings
W katalogach poniżej **zakazane** są importy `homeassistant`:
- `core/`
- `transport/`
- `registers/`
- `scanner/`

### 3.2 Coordinator nie robi Modbusa bezpośrednio
`coordinator/` nie wykonuje:
- `read_*registers`, `read_coils`, `write_register`
- wywołań `pymodbus`/socket

Coordinator deleguje do `core/client.py`:
- `read_snapshot()`
- `write_register()`
- `scan_capabilities()`

### 3.3 Platformy HA nie dekodują raw rejestrów
Platformy czytają gotowe dane z `coordinator.data` / `DeviceSnapshot`.

### 3.4 Transport nie zna ThesslaGreen
`transport/` zna tylko Modbus (adres/funkcja/timeout/retry/odpowiedzi).

### 3.5 Registers nie wykonuje I/O
`registers/` = definicje + walidacja + codec + planner + lookup.

## 4) Decyzja migracyjna
- Kod legacy usuwamy etapami aż do pełnego wygaszenia.
- **Nie dodajemy shimów migracyjnych** (także krótkotrwałych).
- Po przeniesieniu funkcji usuwamy jej odpowiednik legacy w tym samym PR.

## 5) Jedno źródło prawdy dla rejestrów
`registers/thessla_green_registers_full.json` jest jedynym źródłem prawdy dla definicji rejestrów.

Konsekwencje:
- brak duplikowania adresów/definicji w Pythonie,
- każda zmiana rejestru = JSON + walidacja + testy.

## 6) Minimalny standard testów
### Tier 1 (unit, bez HA/bez sieci)
- registers, codec, planner, retry, errors, const

### Tier 2 (mock I/O)
- transport, scanner, core/client, coordinator (z mock clientem), service handlers

### Tier 3 (real HA)
- setup/unload/reload, config flow/options/reauth, platformy, diagnostics, services

Dodatkowo:
- zakaz `platform_stubs.py` i patchowania `sys.modules` dla HA,
- testy mają sprawdzać zachowanie biznesowe, nie tylko coverage.

## 7) Definition of Done dla każdego PR
- `ruff` przechodzi
- `pytest` dla dotkniętego tieru przechodzi
- brak nowych importów HA w `core/transport/registers/scanner`
- brak direct Modbus I/O w `coordinator/platformach`
- zachowana kompatybilność funkcjonalna (potwierdzona testami)

## 8) Kolejność prac (skrót)
1. Test foundation (PHCC/markery/komendy)
2. Platform tests na real HA (bez stubów)
3. `core/errors` + `transport/retry`
4. split `registers` (definition/codec/planner)
5. package `transport`
6. `core/client` + delegacja z coordinatora
7. scanner cleanup
8. services cleanup
9. config flow cleanup
10. coordinator cleanup
