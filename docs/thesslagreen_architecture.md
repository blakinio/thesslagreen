# ThesslaGreen Modbus — Architektura docelowa

## Cel

Celem architektury jest rozdzielenie integracji na jasne warstwy tak, aby Home Assistant był cienkim adapterem, a logika urządzenia, Modbus, rejestrów i skanowania była poza warstwą HA.

Docelowy kierunek:

```text
Platformy HA
    ↓
Coordinator
    ↓
Core Client
    ↓
Registers / Scanner
    ↓
Transport
    ↓
pymodbus / socket
```

Najważniejsza zasada:

```text
Home Assistant obsługuje lifecycle, encje, flow i usługi.
Logika domenowa urządzenia nie zależy od Home Assistant.
```

---


## Stan bieżący (2026-04-28)

Repozytorium jest w trakcie etapowej refaktoryzacji. Obok struktury docelowej współistnieją jeszcze elementy przejściowe.

Wymóg bieżący:

```text
coordinator.py nie może być na razie przenoszony
```

Dopuszczalny stan przejściowy:

```text
custom_components/thessla_green_modbus/coordinator.py
custom_components/thessla_green_modbus/coordinator/
```

Niezmiennie obowiązuje zakaz tworzenia:

```text
- legacy modules,
- compatibility shims,
- re-export shims,
- proxy modules.
```

---

## Warstwy

### 1. HA Layer

Pliki i moduły:

```text
__init__.py
config_flow.py
services.py
diagnostics.py
repairs.py
entity.py
sensor.py
binary_sensor.py
switch.py
number.py
select.py
text.py
time.py
fan.py
climate.py
mappings/
```

Odpowiedzialność:

```text
- lifecycle integracji Home Assistant,
- setup/unload/reload,
- config flow/options flow/reauth,
- encje HA,
- usługi HA,
- diagnostyka HA,
- repairs,
- mapowanie danych domenowych na encje.
```

Warstwa HA może importować Home Assistant.

---

### 2. Coordinator — adapter HA

Docelowy katalog:

```text
coordinator/
```

Odpowiedzialność:

```text
- DataUpdateCoordinator,
- update cycle,
- offline/unavailable state,
- logowanie niedostępności i powrotu,
- statystyki runtime,
- scan cache w config entry,
- delegacja do core/client.py.
```

Coordinator nie wykonuje bezpośrednio operacji Modbus.

Dozwolone:

```text
await client.read_snapshot()
await client.write_register(...)
await client.scan_capabilities()
```

Zakazane:

```text
read_holding_registers()
read_input_registers()
read_coils()
write_register() bezpośrednio na transporcie
bezpośrednie użycie pymodbus clienta
raw socket calls
raw register decoding
```

---

### 3. Core — domena urządzenia

Docelowy katalog:

```text
core/
```

Główne pliki:

```text
core/client.py
core/snapshot.py
core/config.py
core/errors.py
```

Odpowiedzialność:

```text
- ThesslaGreenClient,
- connect/close,
- read_snapshot,
- write_register,
- scan_capabilities,
- DeviceSnapshot,
- DeviceIdentity,
- PollStatistics,
- domenowe błędy integracji.
```

Core nie importuje Home Assistant.

Core orkiestruje:

```text
transport + registers/read_planner + registers/codec + scanner
```

---

### 4. Registers — protokół danych

Docelowy katalog:

```text
registers/
```

Odpowiedzialność:

```text
- definicje rejestrów,
- walidacja JSON,
- loader,
- cache definicji,
- codec,
- read planner,
- mapowanie nazwa rejestru → definicja.
```

Źródło prawdy:

```text
registers/thessla_green_registers_full.json
```

Registers nie importuje Home Assistant.

Registers nie wykonuje I/O.

---

### 5. Scanner — wykrywanie urządzenia i capabilities

Docelowy katalog:

```text
scanner/
```

Odpowiedzialność:

```text
- wykrywanie modelu,
- wykrywanie firmware,
- wykrywanie capabilities,
- safe scan,
- normal scan,
- deep scan,
- obsługa unsupported registers,
- scan runtime state.
```

Scanner może używać:

```text
transport/
registers/
core/errors.py
```

Scanner nie importuje Home Assistant.

Scanner nie tworzy encji HA.

---

### 6. Transport — Modbus I/O

Docelowy katalog:

```text
transport/
```

Odpowiedzialność:

```text
- Modbus TCP,
- Modbus RTU,
- RTU-over-TCP,
- raw Modbus responses,
- retry,
- backoff,
- klasyfikacja błędów transportu,
- CRC/framing, jeśli potrzebne.
```

Transport zna tylko Modbus.

Transport nie zna:

```text
- Home Assistant,
- nazw rejestrów ThesslaGreen,
- DeviceSnapshot,
- EntitySpec,
- DeviceCapabilities jako logiki encji.
```

---

## Kierunek zależności

Dozwolony kierunek zależności:

```text
HA Layer
    ↓
Coordinator
    ↓
Core
    ↓
Registers / Scanner
    ↓
Transport
```

Zakazane zależności zwrotne:

```text
core/       → Home Assistant
transport/  → Home Assistant
registers/  → Home Assistant
scanner/    → Home Assistant
transport/  → ThesslaGreen entity/register names
registers/  → transport I/O
platformy   → raw Modbus / raw register decoding
```

---

## Granice odpowiedzialności

### `core/`

```text
- nie importuje Home Assistant,
- zawiera logikę domenową urządzenia,
- udostępnia klienta domenowego dla coordinatora.
```

### `transport/`

```text
- zna tylko Modbus,
- nie zna nazw rejestrów ThesslaGreen,
- nie zna encji HA,
- nie zna DeviceSnapshot.
```

### `registers/`

```text
- nie wykonuje I/O,
- nie zna HA,
- odpowiada za definicje, schema, loader, codec i read plan.
```

### `scanner/`

```text
- nie zna HA,
- nie tworzy encji,
- nie modyfikuje config entry,
- odpowiada tylko za wykrywanie możliwości urządzenia.
```

### `coordinator/`

```text
- jest adapterem HA,
- nie wykonuje direct Modbus I/O,
- nie dekoduje raw rejestrów,
- deleguje do core/client.py.
```

### `mappings/`

```text
- jest warstwą mapowania encji HA,
- może importować klasy HA,
- nie wykonuje Modbus I/O,
- nie dekoduje raw register values.
```

---

## Krytyczne zasady

```text
1. core/transport/registers/scanner nie importują Home Assistant.
2. Coordinator nie wykonuje bezpośrednio Modbus I/O.
3. Platformy HA nie dekodują raw register values.
4. Transport zna tylko Modbus, nie zna ThesslaGreen register names.
5. Registers nie wykonuje I/O.
6. Scanner nie zna HA.
7. mappings/ może importować HA, bo mapuje dane na encje HA.
8. registers/thessla_green_registers_full.json jest jedynym źródłem prawdy dla definicji rejestrów.
```

---

## Brak legacy i brak shimów

Refaktoryzacja ma prowadzić do nowej struktury bez utrzymywania starego kodu jako warstwy kompatybilności.

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

Zasada migracyjna:

```text
1. Przenieś funkcję/klasę do docelowej warstwy.
2. Zaktualizuj wszystkie importy.
3. Przenieś lub popraw testy.
4. Usuń stary moduł/funkcję.
5. Nie zostawiaj shimów.
```

Wyjątek jest dopuszczalny tylko wtedy, gdy Home Assistant wymaga zachowania publicznego API albo istnieje realna migracja użytkowników. Taki wyjątek musi być opisany w kodzie i dokumentacji.

---

## Decyzja migracyjna

```text
- Legacy przepisywane jest do warstw docelowych.
- Nie tworzymy shimów migracyjnych.
- Po przeniesieniu funkcji usuwamy jej odpowiednik legacy.
- Kompatybilność funkcjonalna utrzymywana jest testami behavioral.
- Nie optymalizujemy pod liczbę plików, tylko pod odpowiedzialność modułów.
```
