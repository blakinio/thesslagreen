# Codex Guidelines

## Cel
Dostarczać zmiany zwiększające stabilność, testowalność i klarowny podział odpowiedzialności warstw.

## Zasady nadrzędne
- Optymalizować pod odpowiedzialność modułów, nie pod liczbę plików.
- Utrzymywać kompatybilność funkcjonalną potwierdzoną testami zachowania.
- Preferować małe, etapowe PR-y.

## Co wolno robić
- Przenosić logikę do właściwych warstw.
- Rozbijać monolity na spójne moduły.
- Dodawać testy behavioral i aktualizować dokumentację.

## Czego nie wolno robić
- Dodawać shimów migracyjnych.
- Dodawać importów HA do warstw non-HA.
- Dodawać direct Modbus I/O do coordinatora/platform.
- Zmieniać semantyki rejestrów bez walidacji i testów.

## Zakazane zależności
1. `core/`, `transport/`, `registers/` i `scanner/` nie mogą importować Home Assistant.
2. `coordinator/` nie wykonuje bezpośrednio Modbus I/O.
3. Platformy HA nie dekodują raw register values.
4. `transport/` nie zna nazw rejestrów ThesslaGreen.
5. `registers/` nie wykonuje I/O.
6. `scanner/` nie zna HA.
7. `mappings/` może importować HA (warstwa mapowania encji).
8. Testy platformowe używają real HA/PHCC, bez `platform_stubs.py`.
9. Testy opisują zachowanie, nie pokrycie linii.
10. Nie optymalizować pod liczbę plików, tylko pod odpowiedzialność modułów.

## Docelowa struktura katalogów
```text
custom_components/thessla_green_modbus/
├── __init__.py
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

## Odpowiedzialność każdej warstwy
- **HA layer**: encje, lifecycle entry, flow, services, diagnostics/repairs.
- **Coordinator**: update cycle, availability, delegacja do `core/client.py`.
- **Core**: logika domenowa i kontrakt odczyt/zapis/scan.
- **Registers**: definicje, schema, codec, planner, lookup.
- **Scanner**: wykrywanie możliwości urządzenia bez HA.
- **Transport**: surowa komunikacja Modbus i retry.

## Reguły testów
- Tier 1: pure unit (bez HA/bez pymodbus/bez sieci).
- Tier 2: mock transport / mock pymodbus.
- Tier 3: real HA/PHCC.
- Zakaz `platform_stubs.py` i patchowania `sys.modules` dla HA.
- Zakaz testów coverage-driven.

## Reguły rozmiaru plików
- 0–250 linii: idealnie.
- 250–500: akceptowalne.
- 500–700: tylko przy wysokiej spójności.
- 700+: wymaga uzasadnienia.

## Kolejność PR-ów
1. test foundation
2. platform tests na real HA
3. usunięcie `platform_stubs.py` i uproszczenie `conftest.py`
4. core errors + transport retry
5. registers split
6. transport package
7. core/client.py
8. scanner cleanup
9. services cleanup
10. config flow cleanup
11. coordinator package
12. cleanup coverage-driven tests

## Checklist przed zakończeniem PR
- ruff przechodzi,
- mypy przechodzi, jeśli aktywny,
- pytest dla dotkniętego obszaru przechodzi,
- brak nowych importów HA w core/transport/registers/scanner,
- brak direct Modbus I/O w coordinator/platformach,
- brak testów typu `assert result is not None` bez znaczenia biznesowego,
- brak martwych shimów,
- zachowana kompatybilność config entry/options,
- jeśli zmieniono `services.yaml`, dodano test i dokumentację.
