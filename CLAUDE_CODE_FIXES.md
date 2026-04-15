# thessla_green_modbus — instrukcja napraw dla Claude Code

**Repozytorium:** `github.com/blakinio/thesslagreen` **Branch:** `main` **Wersja docelowa:** `2.3.0`
**Data audytu:** 2026-04-15

Plik zawiera 6 zmian gotowych do wdrożenia. Wszystkie patche są w formacie **SZUKAJ/ZASTĄP** — bloki muszą być stosowane dosłownie (whitespace ma znaczenie). Po każdym patchu jest opcjonalna aktualizacja testu.

**Cele jakościowe (po wdrożeniu wszystkich napraw):**
- 1565+ przechodzących testów,
- zero realnych ostrzeżeń lintera (patrz Fix #6 — przejście z `pyflakes` na `ruff`),
- silver quality scale,
- brak regresji w `test_schedule_summer_regression`, `test_coordinator_io`, `test_register_cache_invalidation`.

**Zalecana kolejność wdrożenia:**
1. Fix #1 (FC03 partial) — najwyższy priorytet, prawdziwa naprawa write-revert bug.
2. Fix #5 (test summer schedule z prawdziwymi nazwami) — podpięcie regresji pod Fix #1.
3. Fix #2 (cache strip z kontrolą FW) — zapobiega utracie rejestrów na innym FW.
4. Fix #4 (set/list w cache) — drobna spójność.
5. Fix #3 (sentinel sensor) — refactor czytelności.
6. Fix #6 (lint) — kosmetyka, ale wymaga decyzji o linterze.

---

## Fix #1 — FC03 partial response: ogon trafiał do `_failed_registers` zamiast do fallbacku indywidualnego

**Plik:** `custom_components/thessla_green_modbus/_coordinator_io.py`

**Problem.** Gdy AirPack4 z FW 3.11 zwraca w batchu FC03 mniej rejestrów niż request (np. 8 z 16 — co realnie się dzieje na summer schedule pod adresami `0x10–0x2B`), brakujący ogon (`register_names[len(response.registers):]`) jest natychmiast oznaczany jako failed przez `_mark_registers_failed`. Skutek: następny poll skipuje cały chunk, write na summer schedule wraca do starej wartości w UI, dopóki failure flag nie zostanie ręcznie wyczyszczony. Gałąź `len == 0` ma już fallback indywidualny — gałąź `0 < n < chunk_count` powinna mieć go też, ograniczony do brakującej części.

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
                            # Partial response (e.g. AirPack4 FW 3.11 returns
                            # fewer registers than requested on schedule_summer
                            # batches). Retry the missing tail with single-
                            # register reads instead of marking it failed —
                            # otherwise post-write refresh skips the chunk and
                            # the UI reverts to the stale value.
                            tail_offset = len(response.registers)
                            tail_names = register_names[tail_offset:]
                            tail_start = chunk_start + tail_offset
                            await self._read_holding_individually(
                                read_method, tail_start, tail_names, data
                            )
                except _PermanentModbusError:
```

### Test do dodania (sekcja 5 zawiera kompletny rewrite test_schedule_summer_regression.py — dodaj tam ten case).

```python
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

    single_values = {18: 303, 19: 404}

    async def _fake_read_with_retry(_read_method, address, count, **_kwargs):
        if count > 1:
            # Batch returns only first 2 of 4 requested registers.
            return SimpleNamespace(registers=[101, 202])
        return SimpleNamespace(registers=[single_values[address]])

    coordinator._read_with_retry = AsyncMock(side_effect=_fake_read_with_retry)
    original_fallback = coordinator._read_holding_individually
    coordinator._read_holding_individually = AsyncMock(wraps=original_fallback)

    data = await coordinator._read_holding_registers_optimized()

    # Fallback called once for the tail (addr 18,19), not for the head.
    coordinator._read_holding_individually.assert_awaited_once()
    fallback_call = coordinator._read_holding_individually.await_args
    assert fallback_call.args[1] == 18  # tail_start
    assert len(fallback_call.args[2]) == 2  # tail_names

    assert data == {
        "schedule_summer_mon_1": 101,
        "schedule_summer_mon_2": 202,
        "schedule_summer_mon_3": 303,
        "schedule_summer_mon_4": 404,
    }
    assert not coordinator._failed_registers
```

---

## Fix #2 — `_apply_scan_cache` strippuje `KNOWN_MISSING_REGISTERS` bez sprawdzania FW urządzenia

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Problem.** Na linii 725-727 strip jest bezwarunkowy. Komentarze w `const.py:204` jasno mówią, że te rejestry są niedostępne **tylko na FW 3.11 / EC2**. Jeśli cache został zbudowany dla nowszego FW (gdzie te rejestry działają), aktualne ładowanie cache'a wytnie je bezpowrotnie do następnego pełnego skanu. Strip powinien być warunkowy względem `firmware` w cache.

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
        # those registers (currently FW 3.11 / EC2 family). Stripping
        # unconditionally would corrupt caches built on newer firmwares where
        # the registers are present, until the next full scan.
        if self._firmware_lacks_known_missing(self.device_info.get("firmware")):
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                if reg_type in self.available_registers:
                    self.available_registers[reg_type].difference_update(names)

        return True

    @staticmethod
    def _firmware_lacks_known_missing(firmware: Any) -> bool:
        """Return True for firmwares that do not expose KNOWN_MISSING_REGISTERS.

        Currently matches FW 3.x / EC2. Extend this when new affected
        firmwares are identified, or invert the check by adding an explicit
        FW allowlist in const.py.
        """
        if not isinstance(firmware, str):
            return False
        major = firmware.strip().split(".", 1)[0]
        return major in {"3"}
```

### Test do dodania (`tests/test_register_cache_invalidation.py`)
```python
def test_apply_scan_cache_keeps_known_missing_for_newer_firmware(
    minimal_coordinator,  # twoja istniejąca fixture
) -> None:
    """Cache built on FW 4.x must NOT have KNOWN_MISSING_REGISTERS stripped."""
    cache = {
        "available_registers": {
            "input_registers": ["compilation_days", "version_patch", "outside_temperature"],
            "holding_registers": ["uart_0_id", "post_heater_on"],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {"firmware": "4.0.1", "serial_number": "Unknown"},
    }
    assert minimal_coordinator._apply_scan_cache(cache) is True
    assert "compilation_days" in minimal_coordinator.available_registers["input_registers"]
    assert "uart_0_id" in minimal_coordinator.available_registers["holding_registers"]


def test_apply_scan_cache_strips_known_missing_for_fw311(
    minimal_coordinator,
) -> None:
    """Cache built on FW 3.11 must have KNOWN_MISSING_REGISTERS stripped."""
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

## Fix #3 — Refactor `_process_register_value`: magic number, prywatny helper, kolejność checków sentinela

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Problem.** W metodzie są trzy osobne checki sentinela (linie 1239, 1252, 1257) w nieoczywistej kolejności, używane jest hardkodowane `32768` zamiast `SENSOR_UNAVAILABLE`, oraz prywatny `definition._is_temperature()` (powinien być publiczny lub flaga w klasie). Refactor scala check sentinela do jednego miejsca, podnosi `_is_temperature` do publicznego API i eliminuje magic number.

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
    # private name. Keep ``_is_temperature`` as the canonical implementation
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

        Order of checks:
        1. DAC range guard (returns None on out-of-range).
        2. Resolve definition (returns False on unknown name — preserves
           legacy contract used by tests).
        3. Sentinel check 0x8000 (SENSOR_UNAVAILABLE):
           - for temperature registers: always None (no sensor / disconnected),
           - for registers in SENSOR_UNAVAILABLE_REGISTERS: SENSOR_UNAVAILABLE,
           - otherwise fall through to normal decode.
        4. Two's-complement adjustment for signed temperatures.
        5. Decode via register definition.
        6. Post-decode SENSOR_UNAVAILABLE check (for definitions that decode
           the sentinel into a non-zero value — keep for backward compat).
        7. Per-register fixups (flow rate two's-complement, enum override).
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

        # --- step 3: sentinel ---
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
            # Falls through: register reports 0x8000 as a real value.

        # --- step 4: two's-complement for signed temperature ---
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

**Uwaga.** `definition._is_temperature()` zostało zachowane w `loader.py` — wszystkie istniejące wywołania wewnątrz loadera nadal działają. Coordinator używa nowej publicznej `is_temperature()`. Po stabilizacji w wersji 2.4.0+ można `_is_temperature` deprecate'ować.

### Test smoke (uzupełnij `tests/test_coordinator.py` lub osobno)
```python
def test_process_register_value_sentinel_temperature_returns_none(coordinator):
    coordinator.data = {}
    assert coordinator._process_register_value("outside_temperature", 32768) is None


def test_process_register_value_sentinel_non_temperature_returns_sentinel(coordinator):
    # duct_supply_temperature is in SENSOR_UNAVAILABLE_REGISTERS but is also a
    # temperature register — the temperature branch wins, returning None.
    assert coordinator._process_register_value("duct_supply_temperature", 32768) is None


def test_process_register_value_no_magic_number_in_module():
    """Guards against re-introduction of the literal 32768 in coordinator."""
    import inspect
    from custom_components.thessla_green_modbus import coordinator as mod
    src = inspect.getsource(mod._process_register_value if hasattr(mod, "_process_register_value")
                            else mod.ThesslaGreenModbusCoordinator._process_register_value)
    assert "32768" not in src
```

---

## Fix #4 — `_apply_scan_cache`: spójność `list | set` przy wczytywaniu

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Problem.** `_normalise_available_registers` przyjmuje `list[str] | set[str]`, ale `_apply_scan_cache` przekazuje przez dict comprehension tylko gałąź `isinstance(value, list)`. Sety są po cichu odrzucane. W praktyce cache zapisywany jest jako lista (`sorted(value)` w `_store_scan_cache`), ale gdyby kiedyś (testy, migracja) trafił do nas dict z setami — utracimy dane. Poprawka jednoliniowa.

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
            "input_registers": {"outside_temperature"},  # set, not list
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

## Fix #5 — `tests/test_schedule_summer_regression.py`: użycie prawdziwych nazw rejestrów

**Plik:** `tests/test_schedule_summer_regression.py`

**Problem.** Test używa zmyślonych nazw `schedule_summer_1`...`schedule_summer_4` na adresach 15-18. W `registers/thessla_green_registers_full.json` realne nazwy to `schedule_summer_mon_1`...`schedule_summer_sun_4` na adresach `0x10–0x2B` (16–43). Test przechodzi tylko dlatego, że `coord._find_register_name` jest mockowany — nie chroni produkcyjnych nazw przed regresją (np. zmiana w JSON nie wywoła failu testu).

### SZUKAJ (cały plik, zastąp jego zawartość)
```python
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException


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
    names = [f"schedule_summer_{i}" for i in range(1, 5)]
    coord.available_registers = {
        "holding_registers": set(names),
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord._register_groups = {"holding_registers": [(15, len(names))]}
    coord._failed_registers = set()
    coord.effective_batch = 20

    addr_to_name = {15 + i: name for i, name in enumerate(names)}
    coord._find_register_name = lambda rt, addr: addr_to_name.get(addr)
    coord._process_register_value = lambda _name, value: value
    coord._clear_register_failure = MagicMock()
    coord._mark_registers_failed = MagicMock(side_effect=lambda regs: coord._failed_registers.update(r for r in regs if r))
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

    single_values = {15: 101, 16: 202, 17: 303, 18: 404}

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
    assert [call.args[1] for call in single_calls] == [15, 16, 17, 18]

    assert data == {
        "schedule_summer_1": 101,
        "schedule_summer_2": 202,
        "schedule_summer_3": 303,
        "schedule_summer_4": 404,
    }
    assert not any(name.startswith("schedule_summer_") for name in coordinator._failed_registers)
```

### ZASTĄP
```python
"""Regression tests for the AirPack4 FW 3.11 batch-read bug on summer schedule.

Background
----------
On firmware 3.11 the device occasionally returns either:
  * a Modbus exception on FC03 batches that span addresses 0x10–0x2B
    (summer schedule), or
  * a partial/empty response with fewer registers than requested.

When that happens, the previous behaviour was to mark the entire chunk (or
its tail) as failed, which caused the next coordinator poll to skip the
chunk entirely. After a write to one of those registers, the UI would
revert to the stale value because no fresh read ever arrived.

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

# Use the real register names from registers/thessla_green_registers_full.json
# at addresses 0x10..0x13 (Monday slots 1..4). This guards against accidental
# renames in the register JSON.
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

    single_values = {
        SUMMER_BASE_ADDR + 0: 101,
        SUMMER_BASE_ADDR + 1: 202,
        SUMMER_BASE_ADDR + 2: 303,
        SUMMER_BASE_ADDR + 3: 404,
    }

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
    assert [call.args[1] for call in single_calls] == [
        SUMMER_BASE_ADDR + i for i in range(4)
    ]

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
    assert len(fallback_call.args[2]) == 2  # tail_names

    assert data == dict(zip(SUMMER_NAMES, [101, 202, 303, 404]))
    assert not coordinator._failed_registers


def test_summer_schedule_register_names_exist_in_registry() -> None:
    """Guard against silent rename of summer schedule registers in JSON."""
    from custom_components.thessla_green_modbus.registers.loader import (
        get_register_definition,
    )

    for name in SUMMER_NAMES:
        definition = get_register_definition(name)
        assert definition is not None, f"Register {name!r} missing from registry JSON"
        assert definition.function == 3, f"{name} must be FC03 (holding register)"
```

---

## Fix #6 — Lint: `pyflakes` nie respektuje `# noqa: F401`, przejdź na `ruff`

**Pliki:** `pyproject.toml` (lub utworzenie `ruff.toml`), `requirements-dev.txt`, ewentualnie usunięcie martwych zmiennych

**Problem.** Bieżące wywołanie `pyflakes` raportuje 4 importy, które już mają intencjonalne `# noqa: F401`:

| Plik | Linia | Import |
| --- | --- | --- |
| `tools/validate_entity_mappings.py` | 31 | `tests.conftest` |
| `tests/conftest.py` | 63 | `homeassistant.util.dt as _ha_dt` |
| `tests/conftest.py` | 636 | `custom_components.thessla_green_modbus.registers.loader` |
| `tests/test_climate.py` | 343 | `SPECIAL_FUNCTION_MAP` |

Wszystkie cztery są **realnie potrzebne** dla side-effectów importu (rejestracja modułów / inicjalizacja). `pyflakes` nie rozpoznaje `# noqa`. `ruff` rozpoznaje, jest szybszy, jest dziś standardem w ekosystemie HA. Dodatkowo wykryje też `_HAS_HA` w `mappings/__init__.py:135-137` — jest ustawiana, ale nigdzie nieużywana (martwy kod).

### Krok 6a — `requirements-dev.txt`: dopisz/podmień

#### SZUKAJ
```
pyflakes
```

(jeśli linia istnieje — w przeciwnym razie po prostu dodaj poniższe na koniec pliku)

#### ZASTĄP
```
ruff>=0.6.0
```

### Krok 6b — `pyproject.toml`: dodaj sekcję ruff

#### SZUKAJ
```toml
[tool.pytest.ini_options]
```

(zakładając, że taka sekcja istnieje — wstaw blok ruff **przed** nią; jeśli nie istnieje, wstaw blok na końcu pliku)

#### ZASTĄP
```toml
[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = [
    "ProtokolModbusRTU_AirPack4.pdf",
    "airpack4_modbus.json",
]

[tool.ruff.lint]
# F401 = unused import — keep on, but `# noqa: F401` is honored by ruff.
# F403/F405 = star-imports — we use a few in registers/loader.
select = ["E", "F", "W", "I", "B", "UP"]
ignore = [
    "E501",  # line length is enforced by formatter, not the linter
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["B011"]  # asserts are fine in tests
"tools/**" = ["B011"]

[tool.pytest.ini_options]
```

### Krok 6c — usunięcie martwego `_HAS_HA` w `mappings/__init__.py`

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

### Krok 6d — aktualizacja CI / pre-commit (jeśli używasz)

W `.pre-commit-config.yaml`, jeśli istnieje wpis dla `pyflakes` — zamień na:

```yaml
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

### Komenda do uruchomienia po wszystkich zmianach
```bash
ruff check custom_components/ tests/ tools/
ruff format --check custom_components/ tests/ tools/
pytest -q
```

Oczekiwany wynik: `ruff check` → `All checks passed!`, testy → 1565+ passing.

---

## Checklist po wdrożeniu

- [ ] `git diff --stat` pokazuje zmiany w 6 plikach: `_coordinator_io.py`, `coordinator.py`, `registers/loader.py`, `tests/test_schedule_summer_regression.py`, `tests/test_register_cache_invalidation.py`, `pyproject.toml`, `requirements-dev.txt`, `mappings/__init__.py`.
- [ ] `pytest tests/test_schedule_summer_regression.py -v` → 4 testy passed (poprzednio 2).
- [ ] `pytest tests/test_register_cache_invalidation.py -v` → +3 nowe testy passed.
- [ ] `pytest tests/test_coordinator.py -v -k sentinel` → nowe testy sentinela passed.
- [ ] `ruff check custom_components/ tests/ tools/` → `All checks passed!`.
- [ ] `grep -n "32768" custom_components/thessla_green_modbus/coordinator.py` → brak wyników (poza ewentualnymi w komentarzach).
- [ ] `pytest -q` → 1565+ passed, 0 failed.
- [ ] Bump wersji w `manifest.json`: `2.3.0` → `2.3.1`.
- [ ] Dopisz wpis w `CHANGELOG.md` pod `## 2.3.1` z punktami: "Fixed FC03 partial-response tail reverting after write", "Fixed cache strip stripping registers on newer firmware", "Refactored sensor sentinel handling".

---

## Zakres NIEobjęty tym dokumentem

**Polish-language entity ID aliases (41 niedopasowanych entity).** Nie da się tego naprawić bez dumpa `core.entity_registry` z twojego HA. W `mappings/legacy.py:76-81` jest tylko 5 polskich aliasów:
- `rekuperator_moc_odzysku_ciepla`
- `rekuperator_sprawnosc_rekuperatora`
- `rekuperator_pobor_mocy_elektrycznej`
- `rekuperator_nazwa_urzadzenia`
- `rekuperator_predkosc_1`

Aby dopisać brakujące 36, potrzeba:
1. Wyeksportować z HA: `cat /config/.storage/core.entity_registry | jq '.data.entities[] | select(.platform=="thessla_green_modbus") | .entity_id'`
2. Porównać z aktualnymi `unique_id` w `entity_mappings`.
3. Dla każdego polskiego niedopasowania dopisać entry w `LEGACY_ENTITY_ID_OBJECT_ALIASES`.

To zadanie na osobną sesję — wrzuć dump i wygeneruję patch z konkretnymi mapowaniami.
