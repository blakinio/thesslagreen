# ThesslaGreen Modbus — Architektura nadrzędna

## Cel architektury
Oddzielić warstwę Home Assistant od logiki urządzenia/protokołu.
Home Assistant ma pozostać cienką warstwą integracyjną.

## Warstwy
- **HA Layer** — entry lifecycle, platformy encji, config flow, services, diagnostics/repairs.
- **Coordinator** — HA-facing update orchestration, availability/unavailable state, delegacja.
- **Core** — logika domenowa urządzenia (odczyt/zapis/snapshot/capabilities).
- **Registers** — definicje rejestrów, schema, loader, codec, read planner.
- **Scanner** — wykrywanie capabilities/model/firmware.
- **Transport** — Modbus TCP/RTU/RTU-over-TCP + retry/backoff.

## Kierunek zależności
HA platforms → Coordinator → Core → (Registers + Scanner) → Transport → Modbus client/socket.

## Zakazane zależności
- `core/`, `transport/`, `registers/`, `scanner/` nie importują Home Assistant.
- `coordinator/` nie wykonuje direct Modbus I/O.

## Decyzje migracyjne
- Brak shimów migracyjnych.
- Legacy przepisywane do warstw docelowych i usuwane po migracji.

## Zasady niepodlegające negocjacji
- `core/transport/registers/scanner` nie importują Home Assistant.
- `coordinator` nie wykonuje bezpośrednio Modbus I/O.
- Platformy HA nie dekodują raw register values.
- JSON rejestrów jest źródłem prawdy dla definicji rejestrów.
