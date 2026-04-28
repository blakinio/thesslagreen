# Plan refaktoryzacji na gałęzi `test`

Ten dokument wprowadza **szkielet docelowej architektury** dla integracji `thessla_green_modbus`.

## Cel

Rozdzielić odpowiedzialności na warstwy:

- Home Assistant adapter (entry, platformy, config flow, services),
- coordinator (cienka fasada HA),
- core (logika domenowa bez HA),
- transport (Modbus bez wiedzy o rejestrach),
- registers (definicje i codec bez I/O),
- scanner (detekcja urządzenia bez HA),
- mappings (warstwa mapowania encji HA).

## Co zostało przygotowane w tym commicie

Dodano pliki-szkielety dla modułów docelowych:

- `coordinator/` (API koordynatora i cykl życia),
- `core/` (klient domenowy, snapshot, config, errors),
- `transport/` (TCP/RTU/RTU-over-TCP + retry),
- `registers/` (loader, schema, codec, read planner),
- uzupełnienie `scanner/` o brakujące moduły,
- szkielety `diagnostics.py`, `repairs.py`,
- szkielety pomocnicze dla config flow i services.

## Następne kroki

1. Przenieść istniejącą logikę z modułów płaskich do nowych pakietów warstwowych.
2. Dodać testy warstwowe (`unit/`, `transport/`, `scanner/`, `core/`, `coordinator/`, `ha/`, `platforms/`, `services/`).
3. Utrzymać kompatybilność API publicznego integracji i migrację config entry.
4. Po stabilizacji diagnostics/error contract wdrożyć `repairs.py`.
