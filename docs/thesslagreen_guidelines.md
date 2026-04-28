# ThesslaGreen Modbus — Wytyczne implementacyjne

## 1. Twarde reguły
1. Zakaz importów HA w: `core/`, `transport/`, `registers/`, `scanner/`.
2. Zakaz direct Modbus I/O w `coordinator/` i platformach.
3. Zakaz dekodowania raw rejestrów w platformach HA.
4. Zakaz shimów migracyjnych.
5. Zakaz duplikowania definicji rejestrów poza JSON + loader/schema.

## 2. Dozwolone odpowiedzialności (skrót)
- `coordinator/`: lifecycle, update, delegacja do `core/client.py`
- `core/client.py`: connect/close/read_snapshot/write_register/scan_capabilities
- `registers/`: definition/schema/loader/codec/read_planner
- `transport/`: tylko Modbus i retry
- `scanner/`: scan/capabilities/firmware bez HA

## 3. Testy (wymagane)
### Tier 1 (unit)
`registers`, `codec`, `read_planner`, `retry`, `errors`, `const`

### Tier 2 (mock I/O)
`transport`, `scanner`, `core/client`, `coordinator` (mock client), handlers usług

### Tier 3 (real HA)
setup/unload/reload, config flow/options/reauth, platformy, diagnostics, services

Dodatkowo:
- bez `platform_stubs.py`
- bez patchowania `sys.modules` pod HA
- testy mają sprawdzać zachowanie biznesowe

## 4. Definition of Done dla PR
- `ruff` = green
- `pytest` dla dotkniętego tieru = green
- brak nowych importów HA w warstwach non-HA
- brak direct Modbus I/O w coordinator/platformach
- zachowana kompatybilność funkcjonalna (testy)

## 5. Kolejność prac (skrót)
1. Foundation testów (PHCC, markery, komendy)
2. Platform tests na real HA
3. `core/errors` + `transport/retry`
4. split `registers`
5. transport package
6. `core/client` + delegacja z coordinatora
7. scanner cleanup
8. services cleanup
9. config flow cleanup
10. coordinator cleanup
