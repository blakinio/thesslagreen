# ThesslaGreen Modbus — Architektura docelowa

## Cel
Rozdzielić integrację na warstwy tak, aby Home Assistant był cienkim adapterem,
a logika urządzenia/Modbus/rejestrów/scannera była poza HA.

## Warstwy
1. **HA Layer**
   - `__init__.py`, platformy (`sensor.py`, `climate.py`, ...), `config_flow.py`, `services.py`, `diagnostics.py`, `repairs.py`
   - odpowiedzialność: lifecycle HA, encje, flow, usługi

2. **Coordinator (HA adapter)**
   - `coordinator/`
   - odpowiedzialność: `DataUpdateCoordinator`, update cycle, unavailable/offline state, delegacja do `core/client.py`

3. **Core (domena urządzenia)**
   - `core/`
   - odpowiedzialność: `ThesslaGreenClient`, `DeviceSnapshot`, błędy domenowe, orkiestracja read/write/scan

4. **Registers (protokół danych)**
   - `registers/`
   - odpowiedzialność: definicje rejestrów, schema, loader, codec, read planner

5. **Scanner (wykrywanie urządzenia/capabilities)**
   - `scanner/`
   - odpowiedzialność: wykrywanie modelu/firmware/capabilities i obsługa scan flow

6. **Transport (Modbus I/O)**
   - `transport/`
   - odpowiedzialność: TCP/RTU/RTU-over-TCP, retry/backoff, surowe odpowiedzi Modbus

## Kierunek przepływu
Platformy HA → Coordinator → Core Client → Registers/Scanner → Transport → pymodbus/socket

## Krytyczne zasady
- `core/transport/registers/scanner` nie importują Home Assistant.
- Coordinator nie wykonuje bezpośrednio Modbus I/O.
- Platformy nie dekodują raw register values.
- `registers/thessla_green_registers_full.json` to jedyne źródło prawdy dla definicji rejestrów.

## Decyzja migracyjna
- Legacy przepisywane do warstw docelowych, bez shimów migracyjnych.
- Po przeniesieniu funkcji usuwamy jej odpowiednik legacy.
- Kompatybilność funkcjonalna utrzymywana testami behavioral.
