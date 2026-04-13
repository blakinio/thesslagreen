1. Rozbicie god-object coordinator.py (2753 linii)
Plik custom_components/thessla_green_modbus/coordinator.py ma 2753 linie i ~78 metod 
w jednej klasie ThesslaGreenModbusCoordinator. Rozbij go na mixiny lub osobne moduły, 
zachowując pełną kompatybilność API publicznego (coordinator.data, coordinator.async_*):

1. _modbus_io.py  – _read_holding_registers_optimized, _read_coil_registers_optimized,
   _read_input_registers_optimized, _read_discrete_inputs_optimized, 
   _read_holding_individually, _read_with_retry, _call_modbus
2. _register_processing.py – _process_register_value, _find_register_name,
   _mark_registers_failed, _clear_register_failure, SENSOR_UNAVAILABLE handling
3. _capabilities.py – logika detekcji capabilities i _MODEL_POWER_DATA
4. _schedule.py – wszystko związane z schedule_summer/winter i airing
5. coordinator.py – tylko klasa + lifecycle (__init__, async_setup, async_shutdown, 
   _async_update_data)

Wymagania:
- Zero zmian w interfejsie używanym przez platformy (sensor.py, climate.py itd.)
- Zero zmian w zachowaniu poza refaktoringiem
- Usuń `# pragma: no cover` z metod I/O po refaktorze (zobacz prompt #3)
- Wszystkie testy (pytest) muszą przejść bez modyfikacji
- Zero ostrzeżeń pyflakes, zero nowych błędów ruff check --select=F,E,B

2. Centralizacja stubów HA (DRY — 9 duplikatów)
W 9 plikach integracji powtarza się ten sam wzorzec:

    try:
        from homeassistant.util import dt as dt_util
    except (ModuleNotFoundError, ImportError):
        class _DTUtil: ...
        dt_util = _DTUtil()

Stwórz custom_components/thessla_green_modbus/_compat.py który centralizuje WSZYSTKIE 
fallbacki dla testów bez HA (dt_util, EntityCategory, SensorDeviceClass, 
BinarySensorDeviceClass, SensorStateClass, DeviceInfo, EVENT_HOMEASSISTANT_STOP, 
COORDINATOR_BASE). Zamień wszystkie inline try/except w coordinator.py, services.py, 
entity_mappings.py, __init__.py, scanner_core.py na `from ._compat import ...`.

To rozwiąże też 32 błędy ruff E402 (moduły importowane nie na górze pliku), które 
istnieją właśnie z powodu interleaved try/except.

3. Testy dla ścieżek Modbus I/O (usunięcie # pragma: no cover)
Najbardziej krytyczne metody w coordinator.py są wyłączone z pokrycia testami:

- _read_holding_registers_optimized (linia 1597)
- _read_holding_individually (linia 1555) — to jest obejście buga FW 3.11 AirPack4
  gdzie batch read FC03 na schedule_summer addr 15-30 zwraca skorumpowane bajty
- _read_coil_registers_optimized
- _read_input_registers_optimized
- _async_update_data (linia 1349)

Usuń `# pragma: no cover` i dopisz testy jednostkowe w tests/test_coordinator_io.py 
pokrywające przynajmniej:
1. Happy path – batch read zwraca pełną liczbę rejestrów
2. Partial read – response.registers krótszy niż chunk_count → _mark_registers_failed 
   dla brakujących
3. Empty read – len(registers) == 0 → przejście do _read_holding_individually
4. Wyjątek ModbusIOException w batchu → _read_holding_individually (ta gałąź naprawia 
   bug z revertującym się harmonogramem lato na FW 3.11)
5. _PermanentModbusError → rejestry oznaczone jako failed bez fallbacku
6. Ścieżka przez transport.read_holding_registers vs. fallback przez client.*

Używaj AsyncMock dla read_method, wstrzykuj SimpleNamespace(registers=[...]) jako 
response. Cel: ≥90% pokrycia tego pliku.

4. Naprawa RUF012 — mutable class defaults
Dwa miejsca trzymają mutowalne struktury jako class attributes bez ClassVar:

1. custom_components/thessla_green_modbus/binary_sensor.py:169
     _DIAG_NAMES = {"alarm", "error"}
   Zamień na:
     _DIAG_NAMES: ClassVar[frozenset[str]] = frozenset({"alarm", "error"})

2. custom_components/thessla_green_modbus/coordinator.py:1870
     _MODEL_POWER_DATA: dict[int, tuple[float, float]] = {...}
   Zamień typ na ClassVar[Mapping[int, tuple[float, float]]] i owiń w 
   types.MappingProxyType(...) żeby był immutable.

Dodaj `from typing import ClassVar` gdzie trzeba.

5. fan.py — dict lookup zamiast if/elif (SIM116)
W custom_components/thessla_green_modbus/fan.py linie 247-255 jest if/elif dla 
mapowania trybu. Zamień na:

    _MODE_MAP = {0: "auto", 1: "manual", 2: "temporary"}
    
    @property
    def preset_mode(self) -> str | None:
        if "mode" in self.coordinator.data:
            return self._MODE_MAP.get(self.coordinator.data["mode"])
        return None

Sprawdź że testy fan (tests/test_fan.py) przechodzą.

6. Zawężenie except Exception (43 wystąpień)
Przejdź po wszystkich `except Exception` w custom_components/thessla_green_modbus/*.py 
(43 wystąpienia). Dla każdego zamień na konkretny zestaw wyjątków. W kontekście 
Modbus to zazwyczaj:
    (ModbusException, ConnectionException, ModbusIOException, 
     TimeoutError, OSError, ValueError, asyncio.CancelledError)

Tam gdzie naprawdę potrzebny jest szeroki catch (np. handler serwisu który nie może 
pozwolić by HA zawisło), zostaw `except Exception` ALE dodaj komentarz wyjaśniający 
dlaczego + `_LOGGER.exception(...)` zamiast `_LOGGER.error(...)` żeby był traceback.

Nigdy nie połykaj CancelledError — reraise.

7. Ruff auto-fix + pyproject.toml wymuszenie
1. Uruchom: ruff check custom_components/thessla_green_modbus/ --fix
   Naprawi: RUF100 (unused noqa), RUF022 (dunder all sort), RUF019, SIM114.
   
2. Dodaj do pyproject.toml w sekcji [tool.ruff.lint]:
     select = ["F", "E", "W", "B", "SIM", "RUF", "UP", "I"]
     ignore = ["E501"]  # line-too-long — 88 wystąpień, osobne zadanie
   
3. Dodaj pre-commit hook ruff jeśli go jeszcze nie ma w .pre-commit-config.yaml.

4. W CI (.github/workflows) upewnij się że ruff check jest failing gate (obecnie 
   przepuszcza 205 błędów).

8. Walidacja spójności entity_id vs mappings
Z historii projektu: 41 encji różniło się między działającym HA a kodem (polskie 
legacy aliasy jak "tryb_specjalny" vs obecne). Stwórz tools/validate_entity_mappings.py 
który:

1. Wczytuje entity_mappings.py, translations/pl.json, translations/en.json, 
   strings.json, registers/thessla_green_registers_full.json
2. Sprawdza że KAŻDY klucz encji w entity_mappings ma wpis tłumaczenia w pl+en
3. Sprawdza że żadne tłumaczenie nie odnosi się do encji która nie istnieje w mappings
4. Sprawdza że każdy register_name w mappings istnieje w JSON rejestrów
5. Loguje wszystkie legacy aliasy (LEGACY_* w entity_mappings) i weryfikuje że 
   każdy ma aktualny odpowiednik
6. Exit code != 0 przy jakimkolwiek niezgodności

Podłącz ten skrypt jako osobny job w GitHub Actions (.github/workflows).

9. Quick wins (kosmetyka)
ruff check --fix --unsafe-fixes custom_components/thessla_green_modbus/

Zrób osobny commit. Potem ręcznie: 
- 22 SIM102 (collapsible-if) — scal zagnieżdżone if
- 3 SIM108 — zamień if/else na wyrażenie warunkowe
- 30 RUF003 (ambiguous unicode w komentarzach PL) — dodaj `# noqa: RUF003` 
  do komentarzy po polsku albo dodaj do ruff ignore
- RUF059 (unused unpacked variable) — popraw

Priorytetyzacja
Największy ROI: #3 (pokrycie testów ścieżek I/O) bo właśnie tam siedzi bug z rewertem harmonogramu lato, plus #1 (refaktor coordinatora) bo bez tego każda kolejna zmiana jest coraz droższa. #2 i #4-#6 są tanie i idą szybko. #7-#9 to jednorazowe cleanup-y do CI.
