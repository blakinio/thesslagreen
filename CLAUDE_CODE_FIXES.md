# thessla_green_modbus — instrukcja napraw dla Claude Code (v2)

**Repozytorium:** `github.com/blakinio/thesslagreen` **Branch:** `main` **Wersja docelowa:** `2.3.0 → 2.3.1`
**Data audytu:** 2026-04-16 (rev. 2)

**Co się zmieniło vs v1:**
- ⚠️ **Dodany Fix #0 (KRYTYCZNY)** — service `set_airflow_schedule` pisze do nieistniejących rejestrów.
- ✏️ **Przeredagowany Fix #1** — framing "next poll skips chunk" był błędny (`_failed_registers` jest resetowany co poll w `coordinator.py:1132`). Sama łatka pozostaje poprawna — ogon partial response trafia do `data` zamiast znikać.
- ✏️ **Przepisany Fix #6** — `ruff` już jest w `pyproject.toml` z bogatym ruleset. Cztery `# noqa: F401` są OK. Realne findings to czyszczenie Python <3.13 shimów (UP017, UP042, E402) oraz niespójność `target-version` (py312 vs py313).
- 🆕 **Fix #7, #8** — walidacja schematów serwisów (`SET_BYPASS_PARAMETERS`, `SET_GWC_PARAMETERS`).

**Baseline po audycie repo:**
- Testy: 1604 passed, 3 skipped (1607 collected). ✅
- Translations: 1319/1319/1319 kluczy w `strings.json` / `en.json` / `pl.json`. ✅
- Ruff z aktualnym configiem: 7 realnych findings (adresowane w Fix #6).
- Mypy: nieuruchamiany w tym audycie (strict mode w `pyproject.toml`).
- Pyflakes: 4 zbędne importy z `# noqa: F401` — nieistotne (ruff honoruje noqa, to był false positive v1).

**Zalecana kolejność wdrożenia:**
1. **Fix #0** (CRITICAL) — naprawa zepsutego serwisu, najpierw.
2. Fix #1 + Fix #5 — partial response + real register names w teście (sprzężone).
3. Fix #2 + Fix #4 — spójność cache (powiązane przez `_apply_scan_cache`).
4. Fix #3 — refactor sentinel handling.
5. Fix #7 + Fix #8 — walidacja schematów serwisów.
6. Fix #6 — lint cleanup (kosmetyka + usunięcie martwego kodu).

---

## Fix #0 — CRITICAL: `set_airflow_schedule` pisze do nieistniejących rejestrów

**Plik:** `custom_components/thessla_green_modbus/services.py` + pełne przepisanie testów serwisów

**Dowód problemu:**
- Handler (`services.py:416-419`) formatuje nazwy jako `schedule_{day_name}_period{period}_start`, `_end`, `_flow`, `_temp` → np. `schedule_monday_period1_start`.
- W `registers/thessla_green_registers_full.json` **te nazwy nie istnieją**. Realne rejestry harmonogramu to:
  - `schedule_summer_mon_1`..`schedule_summer_sun_4` (addr 0x10–0x2B, FC03, BCD HHMM — czas start slotu),
  - `setting_summer_mon_1`..`setting_summer_sun_4` (addr 0x48–0x63, FC03, % intensywności) + analogicznie `schedule_winter_*` / `setting_winter_*`.
- Weryfikacja (uruchomione lokalnie przy audycie):
  ```
  schedule_monday_period1_start     -> MISSING
  schedule_monday_period1_end       -> MISSING
  schedule_monday_period1_flow      -> MISSING
  schedule_monday_period1_temp      -> MISSING
  schedule_summer_mon_1             -> EXISTS
  setting_summer_mon_1              -> EXISTS
  ```
- Testy (`test_services_handlers.py:263-265`, `test_services_scaling.py:20-24`) **wprost mockują nieistniejące nazwy** (cytat z `test_services_scaling.py:14-16`: "schedule related registers used by the services are added manually as they are not present in the extracted list"). Czyli testy zielone, a produkcja pada cicho w `coordinator.async_write_register` → `get_register_definition(...)` → `KeyError` → log ERROR "Unknown register name".

**Skutek dla użytkownika:** `set_airflow_schedule` / `set_intensity` (alias) nie działa. Od wielu wersji. Brak zgłoszeń prawdopodobnie tylko dlatego, że większość automatyzacji używa entities (number/select), nie service call.

**Dodatkowo:** realny harmonogram na AirPack4 różni się od tego, co zakłada schemat serwisu. Device nie ma osobnych rejestrów `_start`/`_end`/`_flow`/`_temp` na slot — **każdy z 4 slotów na dzień** ma:
- `schedule_<season>_<dow>_<1..4>` — czas START slotu (BCD HHMM, koniec slotu = start kolejnego),
- `setting_<season>_<dow>_<1..4>` — wartość AATT (A = airflow %, TT = zadana temp jako offset).

**Brak odpowiednika** "temperature per slot" jako osobnego rejestru — temp jest częścią AATT (2 niższe bajty). Scheme serwisu tego nie odzwierciedla.

### Krok 0a — przepisz handler na prawdziwe rejestry

#### SZUKAJ (`services.py`, ~120-178 — aktualne schematy)
```python
SET_AIRFLOW_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("day"): vol.In(DAYS_OF_WEEK),
        vol.Required("period"): vol.In(PERIODS),
        vol.Required("start_time"): _CV_TIME,
        vol.Required("end_time"): _CV_TIME,
        vol.Required("airflow_rate"): vol.All(vol.Coerce(int), vol.Range(min=0, max=150)),
        vol.Optional("temperature"): vol.All(vol.Coerce(float), vol.Range(min=16.0, max=30.0)),
    }
)
```

#### ZASTĄP
```python
# AirPack4 harmonogram: 4 sloty na dzień × 2 sezony (summer/winter).
# Każdy slot ma tylko START (czas), koniec = start następnego slotu.
# Intensywność przepływu (%) i odchylenie temperatury siedzą razem w polu AATT
# (osobny rejestr setting_*). Schema to odzwierciedla, nie dorabia fałszywych pól.
#
# - end_time jest IGNOROWANY (nieobsługiwany przez device). Zostawiamy w schema
#   jako Optional deprecated dla wstecznej kompatybilności starych automatyzacji.
#   Jeśli end_time różny od kolejnego start_time, emitujemy warning w log.
_SEASONS = ("summer", "winter")
_DAY_TO_DEVICE_KEY = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}

SET_AIRFLOW_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("day"): vol.In(DAYS_OF_WEEK),
        vol.Required("period"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
        vol.Required("start_time"): _CV_TIME,
        vol.Optional("end_time"): _CV_TIME,  # DEPRECATED — ignored by device
        vol.Required("airflow_rate"): vol.All(vol.Coerce(int), vol.Range(min=0, max=150)),
        vol.Optional("season", default="summer"): vol.In(_SEASONS),
        vol.Optional("temperature"): vol.All(vol.Coerce(float), vol.Range(min=16.0, max=30.0)),
    }
)
```

#### SZUKAJ (handler `set_airflow_schedule` — linie ~371-463)
```python
    async def set_airflow_schedule(call: ServiceCall) -> None:
        """Service to set airflow schedule."""
        entity_ids = _extract_legacy_entity_ids(hass, call)
        day = _normalize_option(call.data["day"])
        period = _normalize_option(call.data["period"])
        start_time = call.data["start_time"]
        end_time = call.data["end_time"]
        airflow_rate = call.data["airflow_rate"]
        temperature = call.data.get("temperature")

        # Convert day name to index
        day_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        day_index = day_map[day]

        # Prepare start/end values as tuples so Register.encode can
        # handle conversion to the device format.
        start_tuple = (start_time.hour, start_time.minute)
        end_tuple = (end_time.hour, end_time.minute)

        # Format times in a user-friendly way for encoding
        start_value = f"{start_tuple[0]:02d}:{start_tuple[1]:02d}"
        end_value = f"{end_tuple[0]:02d}:{end_tuple[1]:02d}"
        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if coordinator:
                # Calculate register names based on day and period
                day_names = [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ]
                day_name = day_names[day_index]

                start_register = f"schedule_{day_name}_period{period}_start"
                end_register = f"schedule_{day_name}_period{period}_end"
                flow_register = f"schedule_{day_name}_period{period}_flow"
                temp_register = f"schedule_{day_name}_period{period}_temp"
                clamped_airflow = _clamp_airflow_rate(coordinator, airflow_rate)

                # Write schedule values relying on register encode logic
                if not await _write_register(
                    coordinator,
                    start_register,
                    start_value,
                    entity_id,
                    "set airflow schedule",
                ):
                    _LOGGER.error("Failed to set schedule start for %s", entity_id)
                    continue
                if not await _write_register(
                    coordinator,
                    end_register,
                    end_value,
                    entity_id,
                    "set airflow schedule",
                ):
                    _LOGGER.error("Failed to set schedule end for %s", entity_id)
                    continue
                if not await _write_register(
                    coordinator,
                    flow_register,
                    clamped_airflow,
                    entity_id,
                    "set airflow schedule",
                ):
                    _LOGGER.error("Failed to set schedule flow for %s", entity_id)
                    continue

                if temperature is not None:
                    if not await _write_register(
                        coordinator,
                        temp_register,
                        temperature,
                        entity_id,
                        "set airflow schedule",
                    ):
                        _LOGGER.error("Failed to set schedule temperature for %s", entity_id)
                        continue

                await coordinator.async_request_refresh()
                _LOGGER.info("Set airflow schedule for %s", entity_id)
```

#### ZASTĄP
```python
    async def set_airflow_schedule(call: ServiceCall) -> None:
        """Service to set airflow schedule for a single slot.

        AirPack4 harmonogram: 4 sloty na dzień × 2 sezony (summer/winter).
        Każdy slot = jedna para rejestrów:
          * ``schedule_<season>_<dow>_<n>`` — czas START (BCD HHMM),
          * ``setting_<season>_<dow>_<n>``  — pole AATT (AA=flow%, TT=temp offset).
        Device NIE ma osobnego rejestru END per slot — koniec slotu jest
        implicit = początek slotu ``n+1`` (lub 23:59 dla slotu 4).
        """
        entity_ids = _extract_legacy_entity_ids(hass, call)
        day = _normalize_option(call.data["day"])
        period = int(call.data["period"])
        season = _normalize_option(call.data.get("season", "summer"))
        start_time = call.data["start_time"]
        airflow_rate = call.data["airflow_rate"]
        temperature = call.data.get("temperature")
        end_time = call.data.get("end_time")

        dow_key = _DAY_TO_DEVICE_KEY[day]
        schedule_register = f"schedule_{season}_{dow_key}_{period}"
        setting_register = f"setting_{season}_{dow_key}_{period}"
        start_value = f"{start_time.hour:02d}:{start_time.minute:02d}"

        if end_time is not None:
            _LOGGER.warning(
                "set_airflow_schedule: end_time is not writable on AirPack4 "
                "(slot end = next slot's start). Ignoring end_time=%s.",
                end_time,
            )

        for entity_id in entity_ids:
            coordinator = _get_coordinator_from_entity_id(hass, entity_id)
            if not coordinator:
                continue

            # Guard: skip silently if device doesn't expose these registers
            # (e.g. firmware variant without full schedule support).
            holding = coordinator.available_registers.get("holding_registers", set())
            if schedule_register not in holding or setting_register not in holding:
                _LOGGER.error(
                    "set_airflow_schedule: %s or %s not available on %s — "
                    "aborting",
                    schedule_register,
                    setting_register,
                    entity_id,
                )
                continue

            clamped_airflow = _clamp_airflow_rate(coordinator, airflow_rate)

            # 1) Write slot start time (BCD HHMM).
            if not await _write_register(
                coordinator,
                schedule_register,
                start_value,
                entity_id,
                "set airflow schedule start",
            ):
                _LOGGER.error("Failed to set schedule start for %s", entity_id)
                continue

            # 2) Write AATT = (airflow % << 8) | (temp offset).
            #    Temp offset encoding: 0..39 reprezentuje 16.0..35.5 °C (krok 0.5).
            if temperature is not None:
                temp_byte = max(0, min(39, int(round((temperature - 16.0) * 2))))
            else:
                # Preserve existing TT byte when only airflow is updated.
                current = coordinator.data.get(setting_register) if coordinator.data else None
                temp_byte = int(current) & 0xFF if isinstance(current, int) else 0
            aatt_value = ((clamped_airflow & 0xFF) << 8) | (temp_byte & 0xFF)

            if not await _write_register(
                coordinator,
                setting_register,
                aatt_value,
                entity_id,
                "set airflow schedule AATT",
            ):
                _LOGGER.error("Failed to set schedule AATT for %s", entity_id)
                continue

            await coordinator.async_request_refresh()
            _LOGGER.info(
                "Set airflow schedule [%s %s slot %d] start=%s flow=%d%% on %s",
                season,
                dow_key,
                period,
                start_value,
                clamped_airflow,
                entity_id,
            )
```

### Krok 0b — `services.yaml`: uaktualnij definicje pól

#### SZUKAJ (`services.yaml`, sekcja `set_airflow_schedule`)
Wyszukaj blok `set_airflow_schedule:` i porównaj pola z nowym schematem. Usuń `end_time` z pól wymaganych (lub oznacz jako deprecated), dodaj `season` z `default: summer` i opcjami `[summer, winter]`, zmień `period` na numeric `1..4`.

### Krok 0c — przepisz testy na prawdziwe rejestry

Otwórz `tests/test_services_scaling.py` linie ~17-25 i usuń fake mapping:

#### SZUKAJ
```python
# Build a register map similar to what the coordinator exposes.  The schedule
# related registers used by the services are added manually as they are not
# present in the extracted list.
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}
HOLDING_REGISTERS.update(
    {
        "schedule_monday_period1_start": 0,
        "schedule_monday_period1_end": 1,
        "schedule_monday_period1_flow": 2,
        "schedule_monday_period1_temp": 3,
    }
)
```

#### ZASTĄP
```python
# Real AirPack4 holding register map (no fakes). Schedule services write to
# schedule_<season>_<dow>_<n> and setting_<season>_<dow>_<n>.
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}
```

W `tests/test_services_handlers.py` linie ~263-265 zmień asercje:

#### SZUKAJ
```python
    assert "schedule_monday_period1_start" in written
    assert "schedule_monday_period1_end" in written
    assert "schedule_monday_period1_flow" in written
```

#### ZASTĄP
```python
    # Service now writes 2 real registers per slot (start + AATT).
    assert "schedule_summer_mon_1" in written
    assert "setting_summer_mon_1" in written
    # end_time is not writable (slot boundary is implicit).
    assert not any(k.endswith("_period1_end") for k in written)
```

Identyczne poprawki zastosuj w `test_set_airflow_schedule_with_temperature`, `test_set_airflow_schedule_clamp_rate`, `test_set_airflow_schedule_write_failure`, `test_set_airflow_schedule_clamp_bad_min`, `test_set_airflow_schedule_clamp_bad_max`, `test_set_airflow_schedule_clamp_inverted_bounds` oraz w `tests/test_misc_helpers.py` linie 119, 127, 135, 145, 154 (zmień `"schedule_monday_period1_start"` na `"schedule_summer_mon_1"`).

### Krok 0d — regresyjny test integrujący z JSONem rejestrów

Dodaj nowy test gwarantujący, że wszystkie nazwy konstruowane przez service faktycznie istnieją w registry:

**Nowy plik: `tests/test_services_register_names_exist.py`**
```python
"""Guard: every register name a service writes to must exist in the registry."""

from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.registers.loader import (
    get_register_definition,
)

_SEASONS = ("summer", "winter")
_DOW = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_SLOTS = (1, 2, 3, 4)


@pytest.mark.parametrize("season", _SEASONS)
@pytest.mark.parametrize("dow", _DOW)
@pytest.mark.parametrize("slot", _SLOTS)
def test_schedule_register_exists(season: str, dow: str, slot: int) -> None:
    name = f"schedule_{season}_{dow}_{slot}"
    definition = get_register_definition(name)
    assert definition is not None, f"Service writes to nonexistent register {name!r}"
    assert definition.function == 3


@pytest.mark.parametrize("season", _SEASONS)
@pytest.mark.parametrize("dow", _DOW)
@pytest.mark.parametrize("slot", _SLOTS)
def test_setting_register_exists(season: str, dow: str, slot: int) -> None:
    name = f"setting_{season}_{dow}_{slot}"
    definition = get_register_definition(name)
    assert definition is not None, f"Service writes to nonexistent register {name!r}"
    assert definition.function == 3
```

Po wdrożeniu tego testu przyszłe zmiany schematu harmonogramu nie będą w stanie przepuścić regresji przez CI.

---

## Fix #1 — FC03 partial response: ogon tracony zamiast fallbacku indywidualnego

**Plik:** `custom_components/thessla_green_modbus/_coordinator_io.py`

**Problem (poprawione framing v1).** Gdy AirPack4 z FW 3.11 zwraca w batchu FC03 mniej rejestrów niż request (np. 8 z 16), brakujący ogon (`register_names[len(response.registers):]`) jest oznaczany jako failed przez `_mark_registers_failed`. Nie ma fallbacku na pojedyncze ready.

**Uwaga do v1:** `_failed_registers` jest resetowany co poll (`coordinator.py:1132`), więc flaga "failed" w praktyce działa tylko w obrębie pojedynczego cyklu update. Mimo to fix jest potrzebny: **brak fallbacku = brak wartości w `data`** → coordinator nie dostanie świeżej wartości po zapisie → UI zostaje ze starą (z poprzedniego polla, jeśli akurat wtedy batch nie był partial). To jest właśnie zaobserwowany "write-revert" na summer schedule.

### SZUKAJ
```python
                    if len(response.registers) < chunk_count:
                        if len(response.registers) == 0:
                            # Batch returned nothing — fall back to individual reads
                            await self._read_holding_individually(
                                read_method, chunk_start, register_names, data
                            )
                        else:
                            missing = register_names[len(response.registers) :]
                            self._mark_registers_failed(missing)
                except _PermanentModbusError:
```

### ZASTĄP
```python
                    if len(response.registers) < chunk_count:
                        if len(response.registers) == 0:
                            # Batch returned nothing — fall back to individual reads
                            await self._read_holding_individually(
                                read_method, chunk_start, register_names, data
                            )
                        else:
                            # Partial response (e.g. AirPack4 FW 3.11 on
                            # schedule_summer). Retry the missing tail with
                            # single-register reads instead of dropping it —
                            # otherwise the post-write refresh returns stale
                            # data and the UI appears to revert the write.
                            tail_offset = len(response.registers)
                            tail_names = register_names[tail_offset:]
                            tail_start = chunk_start + tail_offset
                            await self._read_holding_individually(
                                read_method, tail_start, tail_names, data
                            )
                except _PermanentModbusError:
```

Test regresyjny — patrz Fix #5.

---

## Fix #2 — Cache strip `KNOWN_MISSING_REGISTERS` bez kontroli FW

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Problem.** Linia 725-727 stripuje bezwarunkowo. Komentarze w `const.py:204` jasno mówią "FW 3.11 / EC2". Cache zbudowany na nowszym FW (gdzie rejestry są) zostanie okaleczony do następnego pełnego skanu.

### SZUKAJ
```python
        if self.device_info.get("serial_number") and self.device_info["serial_number"] != "Unknown":
            self.available_registers["input_registers"].add("serial_number")

        for reg_type, names in KNOWN_MISSING_REGISTERS.items():
            if reg_type in self.available_registers:
                self.available_registers[reg_type].difference_update(names)

        return True
```

### ZASTĄP
```python
        if self.device_info.get("serial_number") and self.device_info["serial_number"] != "Unknown":
            self.available_registers["input_registers"].add("serial_number")

        # Only strip KNOWN_MISSING_REGISTERS for firmwares that actually lack
        # those registers (currently FW 3.x / EC2 family). Stripping
        # unconditionally would corrupt caches built on newer firmwares.
        if self._firmware_lacks_known_missing(self.device_info.get("firmware")):
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                if reg_type in self.available_registers:
                    self.available_registers[reg_type].difference_update(names)

        return True

    @staticmethod
    def _firmware_lacks_known_missing(firmware: Any) -> bool:
        """Return True for firmwares that do not expose KNOWN_MISSING_REGISTERS.

        Currently matches FW 3.x / EC2. Extend this when new affected
        firmwares are identified.
        """
        if not isinstance(firmware, str):
            return False
        major = firmware.strip().split(".", 1)[0]
        return major in {"3"}
```

### Test (`tests/test_register_cache_invalidation.py`)
```python
def test_apply_scan_cache_keeps_known_missing_for_newer_firmware(minimal_coordinator):
    cache = {
        "available_registers": {
            "input_registers": ["compilation_days", "outside_temperature"],
            "holding_registers": ["uart_0_id"],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {"firmware": "4.0.1", "serial_number": "Unknown"},
    }
    assert minimal_coordinator._apply_scan_cache(cache) is True
    assert "compilation_days" in minimal_coordinator.available_registers["input_registers"]
    assert "uart_0_id" in minimal_coordinator.available_registers["holding_registers"]


def test_apply_scan_cache_strips_known_missing_for_fw311(minimal_coordinator):
    cache = {
        "available_registers": {
            "input_registers": ["compilation_days", "outside_temperature"],
            "holding_registers": ["uart_0_id"],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {"firmware": "3.11", "serial_number": "Unknown"},
    }
    assert minimal_coordinator._apply_scan_cache(cache) is True
    assert "compilation_days" not in minimal_coordinator.available_registers["input_registers"]
    assert "uart_0_id" not in minimal_coordinator.available_registers["holding_registers"]
    assert "outside_temperature" in minimal_coordinator.available_registers["input_registers"]
```

---

## Fix #3 — Refactor `_process_register_value`: magic number, prywatny helper, kolejność sentinela

**Plik:** `custom_components/thessla_green_modbus/coordinator.py` + `registers/loader.py`

**Problem.** Metoda ma trzy osobne checki sentinela (linie 1239, 1252, 1257), używa `32768` zamiast `SENSOR_UNAVAILABLE`, oraz prywatnego `definition._is_temperature()`.

### Krok 3a — `registers/loader.py`: alias publiczny

#### SZUKAJ
```python
    def _is_temperature(self) -> bool:
        """Return True when the register represents a temperature value."""

        if self.unit and "°" in self.unit:
            return True
        return "temperature" in self.name
```

#### ZASTĄP
```python
    def _is_temperature(self) -> bool:
        """Return True when the register represents a temperature value."""

        if self.unit and "°" in self.unit:
            return True
        return "temperature" in self.name

    # Public alias — callers outside the loader should not depend on a
    # private name. ``_is_temperature`` remains the canonical implementation
    # to avoid breaking existing internal callers in registers/loader.py.
    def is_temperature(self) -> bool:
        return self._is_temperature()
```

### Krok 3b — `coordinator.py`: refactor metody

#### SZUKAJ
```python
    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Decode a raw register value using its definition."""
        if register_name in {"dac_supply", "dac_exhaust", "dac_heater", "dac_cooler"} and not (
            0 <= value <= 4095
        ):
            _LOGGER.warning("Register %s out of range for DAC: %s", register_name, value)
            return None
        try:
            definition = get_register_definition(register_name)
        except KeyError:
            _LOGGER.error("Unknown register name: %s", register_name)
            return False
        if value == 32768 and definition._is_temperature():
            if _LOGGER.isEnabledFor(logging.DEBUG):  # pragma: no cover
                _LOGGER.debug(
                    "Processed %s: raw=%s value=None (temperature sentinel)",
                    register_name,
                    value,
                )
            return None
        raw_value = value
        if definition._is_temperature() and isinstance(raw_value, int) and raw_value > 32767:
            raw_value -= 65536
        decoded = definition.decode(raw_value)

        if value == SENSOR_UNAVAILABLE and register_name in SENSOR_UNAVAILABLE_REGISTERS:
            if "temperature" in register_name:
                return None
            return SENSOR_UNAVAILABLE

        if decoded == SENSOR_UNAVAILABLE:
            if _LOGGER.isEnabledFor(logging.DEBUG):  # pragma: no cover
                _LOGGER.debug(
                    "Processed %s: raw=%s value=SENSOR_UNAVAILABLE",
                    register_name,
                    value,
                )
            return SENSOR_UNAVAILABLE
        if register_name in {"supply_flow_rate", "exhaust_flow_rate"} and isinstance(decoded, int):
            if decoded > 32767:
                decoded -= 65536

        if definition.enum is not None and isinstance(decoded, str) and isinstance(value, int):
            decoded = value

        _LOGGER.debug("Processed %s: raw=%s value=%s", register_name, value, decoded)
        return decoded
```

#### ZASTĄP
```python
    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Decode a raw register value using its definition.

        Processing order (single place, easier to reason about):
          1. DAC range guard -> None if out of range.
          2. Resolve definition -> False on KeyError (legacy contract).
          3. Sentinel check (0x8000 = SENSOR_UNAVAILABLE):
             * temperature registers -> None,
             * registers in SENSOR_UNAVAILABLE_REGISTERS -> SENSOR_UNAVAILABLE,
             * otherwise fall through (register actually reports 0x8000).
          4. Signed two's complement for temperatures.
          5. Decode via definition.
          6. Post-decode sentinel safety net.
          7. Per-register fixups (flow rate signed, enum override).
        """
        if register_name in {"dac_supply", "dac_exhaust", "dac_heater", "dac_cooler"} and not (
            0 <= value <= 4095
        ):
            _LOGGER.warning("Register %s out of range for DAC: %s", register_name, value)
            return None
        try:
            definition = get_register_definition(register_name)
        except KeyError:
            _LOGGER.error("Unknown register name: %s", register_name)
            return False

        # --- step 3: sentinel (single consolidated branch) ---
        if value == SENSOR_UNAVAILABLE:
            if definition.is_temperature():
                _LOGGER.debug(
                    "Processed %s: raw=%s value=None (temperature sentinel)",
                    register_name,
                    value,
                )
                return None
            if register_name in SENSOR_UNAVAILABLE_REGISTERS:
                _LOGGER.debug(
                    "Processed %s: raw=%s value=SENSOR_UNAVAILABLE",
                    register_name,
                    value,
                )
                return SENSOR_UNAVAILABLE
            # Register actually reports 0x8000 as a real value — fall through.

        # --- step 4: two's complement for signed temperature ---
        raw_value = value
        if definition.is_temperature() and isinstance(raw_value, int) and raw_value > 32767:
            raw_value -= 65536

        # --- step 5: decode ---
        decoded = definition.decode(raw_value)

        # --- step 6: post-decode sentinel safety net ---
        if decoded == SENSOR_UNAVAILABLE:
            _LOGGER.debug(
                "Processed %s: raw=%s value=SENSOR_UNAVAILABLE (post-decode)",
                register_name,
                value,
            )
            return SENSOR_UNAVAILABLE

        # --- step 7: per-register fixups ---
        if register_name in {"supply_flow_rate", "exhaust_flow_rate"} and isinstance(decoded, int):
            if decoded > 32767:
                decoded -= 65536

        if definition.enum is not None and isinstance(decoded, str) and isinstance(value, int):
            decoded = value

        _LOGGER.debug("Processed %s: raw=%s value=%s", register_name, value, decoded)
        return decoded
```

### Test smoke
```python
def test_process_register_value_sentinel_temperature_returns_none(coordinator):
    assert coordinator._process_register_value("outside_temperature", 32768) is None


def test_process_register_value_no_magic_number_in_source():
    """Regression guard against re-introduction of the literal 32768."""
    import inspect
    from custom_components.thessla_green_modbus.coordinator import (
        ThesslaGreenModbusCoordinator,
    )
    src = inspect.getsource(
        ThesslaGreenModbusCoordinator._process_register_value
    )
    assert "32768" not in src
```

---

## Fix #4 — `_apply_scan_cache`: spójność `list | set`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Problem.** `_normalise_available_registers` przyjmuje `list[str] | set[str]`, ale `_apply_scan_cache` przepuszcza tylko `isinstance(value, list)`. Sety są cicho odrzucane. Jednolinijkowa poprawka.

### SZUKAJ
```python
        try:
            self.available_registers = self._normalise_available_registers(
                {key: value for key, value in available.items() if isinstance(value, list)}
            )
        except (TypeError, ValueError):
            return False
```

### ZASTĄP
```python
        try:
            self.available_registers = self._normalise_available_registers(
                {
                    key: value
                    for key, value in available.items()
                    if isinstance(value, (list, set))
                }
            )
        except (TypeError, ValueError):
            return False
```

### Test
```python
def test_apply_scan_cache_accepts_set_values(minimal_coordinator):
    cache = {
        "available_registers": {
            "input_registers": {"outside_temperature"},
            "holding_registers": [],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {"serial_number": "Unknown"},
    }
    assert minimal_coordinator._apply_scan_cache(cache) is True
    assert "outside_temperature" in minimal_coordinator.available_registers["input_registers"]
```

---

## Fix #5 — `tests/test_schedule_summer_regression.py`: prawdziwe nazwy + test partial response

**Plik:** `tests/test_schedule_summer_regression.py`

**Problem.** Test używa zmyślonych `schedule_summer_1`..`_4` na addr 15-18. Realne nazwy to `schedule_summer_mon_1`..`_4` na addr 0x10-0x13 (16-19). Test przechodzi tylko przez mock — nie chroni produkcji.

### ZASTĄP CAŁĄ ZAWARTOŚĆ pliku
```python
"""Regression tests for the AirPack4 FW 3.11 batch-read bug on summer schedule.

Background
----------
On firmware 3.11 the device occasionally returns either:
  * a Modbus exception on FC03 batches spanning addresses 0x10–0x2B
    (summer schedule), or
  * a partial/empty response with fewer registers than requested.

Previous behavior silently dropped the missing tail, so the fresh value
written by the user never appeared in ``data`` and the UI showed the stale
value until a clean batch read eventually succeeded — the observed
"write-revert" bug.

These tests pin the recovery contract:
  * empty batch  -> full fallback to individual reads,
  * raises       -> full fallback to individual reads,
  * partial head -> tail-only fallback to individual reads.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException

# Real register names from registers/thessla_green_registers_full.json at
# addresses 0x10..0x13 (Monday slots 1..4). Uses the canonical names so a
# rename in the JSON would break this test — which is the point.
SUMMER_NAMES = [
    "schedule_summer_mon_1",
    "schedule_summer_mon_2",
    "schedule_summer_mon_3",
    "schedule_summer_mon_4",
]
SUMMER_BASE_ADDR = 0x10  # 16


@pytest.fixture
def coordinator() -> ThesslaGreenModbusCoordinator:
    coord = ThesslaGreenModbusCoordinator(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=5,
        retry=1,
    )
    coord.available_registers = {
        "holding_registers": set(SUMMER_NAMES),
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord._register_groups = {"holding_registers": [(SUMMER_BASE_ADDR, len(SUMMER_NAMES))]}
    coord._failed_registers = set()
    coord.effective_batch = 20

    addr_to_name = {SUMMER_BASE_ADDR + i: name for i, name in enumerate(SUMMER_NAMES)}
    coord._find_register_name = lambda rt, addr: addr_to_name.get(addr)
    coord._process_register_value = lambda _name, value: value
    coord._clear_register_failure = MagicMock()
    coord._mark_registers_failed = MagicMock(
        side_effect=lambda regs: coord._failed_registers.update(r for r in regs if r)
    )
    return coord


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_mode", ["raises", "empty"])
async def test_schedule_summer_batch_bug_falls_back_to_individual_reads(
    coordinator: ThesslaGreenModbusCoordinator,
    batch_mode: str,
) -> None:
    coordinator._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    coordinator.client = None

    single_values = {SUMMER_BASE_ADDR + i: v for i, v in enumerate([101, 202, 303, 404])}

    async def _fake_read_with_retry(_read_method, address, count, **_kwargs):
        if count > 1:
            if batch_mode == "raises":
                raise ModbusIOException("corrupt")
            return SimpleNamespace(registers=[])
        return SimpleNamespace(registers=[single_values[address]])

    coordinator._read_with_retry = AsyncMock(side_effect=_fake_read_with_retry)
    original_fallback = coordinator._read_holding_individually
    coordinator._read_holding_individually = AsyncMock(wraps=original_fallback)

    data = await coordinator._read_holding_registers_optimized()

    coordinator._read_holding_individually.assert_awaited_once()
    single_calls = [
        call
        for call in coordinator._read_with_retry.await_args_list
        if call.args[2] == 1
    ]
    assert [call.args[1] for call in single_calls] == [SUMMER_BASE_ADDR + i for i in range(4)]
    assert data == dict(zip(SUMMER_NAMES, [101, 202, 303, 404]))
    assert not any(name.startswith("schedule_summer_") for name in coordinator._failed_registers)


@pytest.mark.asyncio
async def test_schedule_summer_partial_batch_falls_back_for_tail_only(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    """FW 3.11 returns 2 of 4 registers — tail must NOT be marked failed."""
    coordinator._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    coordinator.client = None

    tail_singles = {SUMMER_BASE_ADDR + 2: 303, SUMMER_BASE_ADDR + 3: 404}

    async def _fake_read_with_retry(_read_method, address, count, **_kwargs):
        if count > 1:
            return SimpleNamespace(registers=[101, 202])
        return SimpleNamespace(registers=[tail_singles[address]])

    coordinator._read_with_retry = AsyncMock(side_effect=_fake_read_with_retry)
    original_fallback = coordinator._read_holding_individually
    coordinator._read_holding_individually = AsyncMock(wraps=original_fallback)

    data = await coordinator._read_holding_registers_optimized()

    coordinator._read_holding_individually.assert_awaited_once()
    fallback_call = coordinator._read_holding_individually.await_args
    assert fallback_call.args[1] == SUMMER_BASE_ADDR + 2  # tail_start
    assert len(fallback_call.args[2]) == 2
    assert data == dict(zip(SUMMER_NAMES, [101, 202, 303, 404]))
    assert not coordinator._failed_registers


def test_summer_schedule_register_names_exist_in_registry() -> None:
    """Guard against silent rename of summer schedule registers in the JSON."""
    from custom_components.thessla_green_modbus.registers.loader import (
        get_register_definition,
    )

    for name in SUMMER_NAMES:
        definition = get_register_definition(name)
        assert definition is not None, f"Register {name!r} missing from registry JSON"
        assert definition.function == 3
```

---

## Fix #6 — Lint: usuń Python <3.13 compat shimy, wyrównaj `target-version`

**Pliki:** `pyproject.toml`, `custom_components/thessla_green_modbus/_compat.py`, `custom_components/thessla_green_modbus/_coordinator_capabilities.py`, `custom_components/thessla_green_modbus/coordinator.py`, `custom_components/thessla_green_modbus/registers/schema.py`, `custom_components/thessla_green_modbus/mappings/__init__.py`, `tests/test_coordinator_coverage.py`

**Problem (poprawione vs v1).** `ruff` już jest w `pyproject.toml` z ruleset `[F, E, W, B, SIM, RUF, UP, I, PERF, BLE]` i honoruje `# noqa`, więc cztery F401 z v1 **nie są realnym problemem**. Realne findings przy uruchomieniu `ruff check custom_components/ tests/ tools/` to:

- **4× UP017** — `getattr(dt, "UTC", dt.timezone.utc)` i `datetime.UTC if hasattr(...) else timezone.utc` (Python 3.11+ ma `datetime.UTC` bezwarunkowo).
- **2× E402** — importy po kodzie w `_coordinator_capabilities.py:10-11` (bezpośrednio po linii `UTC = ...`).
- **1× UP042** — `class StrEnum(str, Enum)` fallback w `registers/schema.py:28` (Python 3.11+ ma `enum.StrEnum` bezwarunkowo).

**Plus niespójność wersji:**
- `pyproject.toml:project.requires-python = ">=3.13"` ✅
- `pyproject.toml:tool.ruff.target-version = "py312"` ❌ (powinno być `py313`)
- `pyproject.toml:tool.black.target-version = ["py313"]` ✅
- `pyproject.toml:tool.mypy.python_version = "3.13"` ✅

Plus **martwy kod** wykryty przez vulture:
- `mappings/__init__.py:135-137`: `_HAS_HA` ustawione, nigdzie nieużyte.
- `_compat.py:1-144`: cały plik to compat shim dla Pythona <3.11 / HA niezainstalowanego. Przy `requires-python = ">=3.13"` to w większości martwy kod (same HA stub fallbacki są potrzebne tylko dla trybu testów bez HA — zostawiamy).

### Krok 6a — `pyproject.toml`: wyrównaj target-version

#### SZUKAJ
```toml
[tool.ruff]
line-length = 100
target-version = "py312"
src = ["custom_components", "tests", "tools"]
```

#### ZASTĄP
```toml
[tool.ruff]
line-length = 100
target-version = "py313"
src = ["custom_components", "tests", "tools"]
```

### Krok 6b — `_compat.py`: usuń `UTC` shim, zostaw HA stubby

#### SZUKAJ
```python
"""Compatibility helpers for running integration code with/without Home Assistant."""

from __future__ import annotations

import datetime as dt
from typing import Any

UTC = getattr(dt, "UTC", dt.timezone.utc)

try:
    from homeassistant.util import dt as dt_util
except (ModuleNotFoundError, ImportError):
    class _DTUtil:
```

#### ZASTĄP
```python
"""Compatibility helpers for running integration code with/without Home Assistant."""

from __future__ import annotations

import datetime as dt
from datetime import UTC
from typing import Any

try:
    from homeassistant.util import dt as dt_util
except (ModuleNotFoundError, ImportError):
    class _DTUtil:
```

### Krok 6c — `_coordinator_capabilities.py`: usuń UTC shim, przenieś importy na górę

#### SZUKAJ
```python
from datetime import datetime, timezone

UTC = datetime.UTC if hasattr(datetime, "UTC") else timezone.utc
from types import MappingProxyType
from typing import Any, ClassVar
```

#### ZASTĄP
```python
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, ClassVar
```

### Krok 6d — `coordinator.py`: usuń UTC shim

#### SZUKAJ
```python
UTC = getattr(dt, "UTC", dt.timezone.utc)
```

#### ZASTĄP
```python
from datetime import UTC
```

(umieść ten import razem z innymi importami na górze pliku; obecna linia `UTC = ...` na poziomie modułu idzie do usunięcia)

### Krok 6e — `registers/schema.py`: usuń StrEnum fallback

#### SZUKAJ
```python
try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11
    class StrEnum(str, Enum):
        """Fallback StrEnum for older Python versions."""
```

#### ZASTĄP
```python
from enum import StrEnum
```

(Uwaga: jeśli dalej w pliku istnieje `pragma: no cover` closing block fallback class, również usuń — `ruff --fix` wykona to automatycznie.)

### Krok 6f — `tests/test_coordinator_coverage.py`: usuń UTC shim

#### SZUKAJ
```python
from datetime import datetime, timezone

UTC = datetime.UTC if hasattr(datetime, "UTC") else timezone.utc
```

#### ZASTĄP
```python
from datetime import UTC, datetime
```

### Krok 6g — `mappings/__init__.py`: usuń martwy `_HAS_HA`

#### SZUKAJ
```python
try:  # pragma: no cover - handle partially initialized module
    _HAS_HA = importlib.util.find_spec("homeassistant") is not None
except (ImportError, ValueError):
    _HAS_HA = False

_run_build_entity_mappings()
```

#### ZASTĄP
```python
_run_build_entity_mappings()
```

### Komenda weryfikacyjna
```bash
ruff check custom_components/ tests/ tools/
```
Oczekiwany wynik: `All checks passed!`.

---

## Fix #7 — `SET_BYPASS_PARAMETERS_SCHEMA`: zbyt restrykcyjny `min_outdoor_temperature`

**Plik:** `custom_components/thessla_green_modbus/services.py`

**Problem.** Bypass na AirPack4 włącza się powyżej `min_outdoor_temperature` (free cooling — przepuszcza powietrze obok wymiennika, gdy na zewnątrz chłodno, a w środku ciepło). W praktyce użytkownicy ustawiają ten próg od ~10°C do ~22°C, ale rejestr urządzenia akceptuje również wartości ujemne (niektóre scenariusze grzewcze/zimowe), i górna granica 40°C nie ma sensu fizycznego w Polsce. Obecny schemat `Range(min=10.0, max=40.0)` odrzuca sensowne wartości ujemne.

### SZUKAJ
```python
SET_BYPASS_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("mode"): vol.In(BYPASS_MODES),
        vol.Optional("min_outdoor_temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=10.0, max=40.0)
        ),
    }
)
```

### ZASTĄP
```python
SET_BYPASS_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("mode"): vol.In(BYPASS_MODES),
        # AirPack4 accepts -20..40 °C; expose the full device range.
        vol.Optional("min_outdoor_temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=-20.0, max=40.0)
        ),
    }
)
```

**Weryfikacja w PDF:** `ProtokolModbusRTU_AirPack4.pdf` → rejestr `min_outdoor_temperature` / `air_temperature_summer_free_cooling`. Przed commitem sprawdź zakres zadeklarowany przez ThesslaGreen. Jeśli PDF mówi inaczej, dostosuj `min`/`max`. Jeśli PDF nie precyzuje — zostaw -20..40 jako konserwatywny zakres fizyczny.

---

## Fix #8 — `SET_GWC_PARAMETERS_SCHEMA`: brak walidacji `min < max`

**Plik:** `custom_components/thessla_green_modbus/services.py`

**Problem.** Schema pozwala ustawić `min_air_temperature=20` i `max_air_temperature=30` — ale **nic nie brania** podania `min=20, max=15` (obie wartości w swoich zakresach, ale para nielegalna). Bez cross-field validation user może zapisać coś, co wyłącza GWC na stałe (urządzenie zwykle odrzuca, ale niektóre FW akceptują w ciszy i potem się dziwi, że GWC nie rusza).

### SZUKAJ
```python
SET_GWC_PARAMETERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
        vol.Required("mode"): vol.In(GWC_MODES),
        vol.Optional("min_air_temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=20.0)
        ),
        vol.Optional("max_air_temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=30.0, max=80.0)
        ),
    }
)
```

### ZASTĄP
```python
def _validate_gwc_temperature_range(data: dict[str, Any]) -> dict[str, Any]:
    """Reject configurations where min_air_temperature >= max_air_temperature."""
    tmin = data.get("min_air_temperature")
    tmax = data.get("max_air_temperature")
    if tmin is not None and tmax is not None and tmin >= tmax:
        raise vol.Invalid(
            f"min_air_temperature ({tmin}) must be strictly less than "
            f"max_air_temperature ({tmax})"
        )
    return data


SET_GWC_PARAMETERS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("entity_id"): _ENTITY_IDS_VALIDATOR,
            vol.Required("mode"): vol.In(GWC_MODES),
            vol.Optional("min_air_temperature"): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=20.0)
            ),
            vol.Optional("max_air_temperature"): vol.All(
                vol.Coerce(float), vol.Range(min=30.0, max=80.0)
            ),
        }
    ),
    _validate_gwc_temperature_range,
)
```

**Uwaga:** aktualne zakresy `min ∈ [0,20]` i `max ∈ [30,80]` są rozłączne, więc `min < max` zawsze prawda. Walidacja jest defensive dla przyszłych zmian schematu (jeśli kiedyś poluzujemy zakresy). Zostawiamy, bo inaczej kod jest nadal podatny na regresję — taniej ustawić teraz.

### Test
```python
def test_gwc_schema_rejects_min_ge_max():
    from custom_components.thessla_green_modbus.services import (
        SET_GWC_PARAMETERS_SCHEMA,
    )
    import voluptuous as vol
    # Relax ranges inline to trigger the cross-field guard in an easily
    # testable way (current disjoint ranges mean min>=max is already
    # impossible through individual Range validators).
    with pytest.raises(vol.Invalid, match="strictly less than"):
        SET_GWC_PARAMETERS_SCHEMA({
            "entity_id": ["sensor.fake"],
            "mode": list(...)[0],  # any valid mode
            "min_air_temperature": 20.0,
            "max_air_temperature": 30.0,
        })
```

(Test wymaga doprecyzowania importu `GWC_MODES` — użyj pierwszego elementu z tupli.)

---

## Checklist po wdrożeniu

- [ ] `git diff --stat` pokazuje zmiany w ~12 plikach.
- [ ] `pytest tests/test_services_register_names_exist.py -v` → 56 tests passed (28 schedule × 2 season + 28 setting × 2 season = 56).
- [ ] `pytest tests/test_services_handlers.py tests/test_services_scaling.py tests/test_misc_helpers.py -v` → brak regresji, wszystkie refactorowane testy zielone.
- [ ] `pytest tests/test_schedule_summer_regression.py -v` → 4 tests passed (było 2).
- [ ] `pytest tests/test_register_cache_invalidation.py -v` → +3 nowe tests passed.
- [ ] `ruff check custom_components/ tests/ tools/` → `All checks passed!`.
- [ ] `grep -rn "schedule_monday_period\|schedule_.*_period[0-9]_start" custom_components/ tests/` → brak wyników (poza ewentualnymi w CHANGELOG).
- [ ] `grep -n "32768" custom_components/thessla_green_modbus/coordinator.py` → brak wyników poza komentarzami.
- [ ] `grep -rn "getattr(dt, .UTC.\|hasattr(datetime, .UTC.)" custom_components/ tests/` → brak wyników.
- [ ] `pytest -q` → co najmniej 1604 passed (baseline) + nowe testy; 0 failed.
- [ ] Bump wersji w `manifest.json`: `2.3.0` → `2.3.1`.
- [ ] Wpis w `CHANGELOG.md` pod `## 2.3.1`:
  - **Fixed:** `set_airflow_schedule` / `set_intensity` silently wrote to nonexistent register names. Services now write to real `schedule_<season>_<dow>_<n>` + `setting_<season>_<dow>_<n>` pairs. Added `season` parameter (default `summer`); `end_time` is now a deprecated no-op (device has no explicit slot-end register). **Breaking for automations** that relied on the old (non-working) behavior.
  - **Fixed:** FC03 partial-response tail was dropped instead of retried individually, causing occasional write-revert on `schedule_summer_*` with AirPack4 FW 3.11.
  - **Fixed:** `KNOWN_MISSING_REGISTERS` was stripped from scan cache regardless of firmware version, corrupting caches on FW 4.x+.
  - **Fixed:** Cross-field validation for `set_gwc_parameters` (min < max) and expanded `set_bypass_parameters` lower bound to support negative outdoor temps.
  - **Refactored:** `_process_register_value` consolidates sentinel handling, removes `32768` magic number and private `_is_temperature()` dependency.
  - **Cleanup:** removed dead Python <3.13 compat shims, aligned `ruff target-version` with `requires-python`, removed unused `_HAS_HA` from `mappings/__init__.py`.

---

## Zakres NIEobjęty tym dokumentem

1. **Polish-language entity ID aliases (41 niedopasowanych entity w HA użytkownika).** W `mappings/legacy.py:76-81` jest tylko 5 polskich aliasów. Aby dopisać brakujące 36, wymagany dump `core.entity_registry`:
   ```bash
   jq '.data.entities[] | select(.platform=="thessla_green_modbus") | .entity_id' /config/.storage/core.entity_registry
   ```
   Po wrzuceniu dumpa → osobny patch.

2. **Audyty nieukończone w tej sesji** (do osobnej rozmowy):
   - `scanner_core.py` (2501 linii) — logika skanera, pełny przegląd.
   - `config_flow.py` (55KB) — flow konfiguracji, walidacje, reauth.
   - `__init__.py` (44KB) — setup, migracje, persistent state.
   - `climate.py` / `fan.py` — spójność z refactorowanym `_process_register_value`.
   - mypy strict mode — uruchomienie i adresowanie błędów typowania.

3. **`_failed_registers` cross-poll semantics.** Flaga jest resetowana co poll w `coordinator.py:1132`, co czyni ją efektywnie bezużyteczną przy obecnej architekturze (każdy rejestr żyje w jednym chunku, więc w tym samym pollu after-mark check nie trafia). Decyzja do podjęcia:
   - **Option A:** usunąć flagę i cały kod ją obsługujący (prostsze, ale tracimy opcję persistencji).
   - **Option B:** utrwalić flagę przez N poll cycles (np. TTL 5 minut) z deliberate clearing po write.
   
   Rekomendacja: Option A — obecny kod to cargo culting, usunięcie uprości ~50 linii w `coordinator.py` i `_coordinator_io.py`.
