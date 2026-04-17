# thessla_green_modbus — instrukcja napraw dla Claude Code (v7 — scalone)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main` (HEAD: `58a81af` — merge PR #1327)
**Wersja docelowa:** `2.3.9 → 2.4.0` (major bump)
**Data audytu:** 2026-04-17

---

## Motywacja

Ten dokument łączy **dwa wątki audytu**:

1. **Dead code cleanup** (wcześniej v5) — osierocone pliki po refactorach (`_scanner_*_mixin.py`, `register_addresses.py`), duplikaty CI (`validate.yaml` + pyflakes), martwy `_compat.py`, niewykorzystana referencja z PDF (`airpack4_modbus.json`).
2. **Production code detox** (wcześniej v6) — produkcja została wygięta żeby pasować do źle napisanych testów. `sys.modules` hacks, monkey-patching bibliotek, skanowanie `tests/` z produkcji, `_PermissiveCapabilities` zwracający True dla wszystkiego.

**Razem: 17 fixów w jednym release.** Duży skok funkcjonalny (2.4.0), ale zero zmian user-visible — integracja zachowuje się identycznie, testy wymagają przepisania.

**Baseline po v2.3.9 (nie ruszać):**
- ✅ Ruff: 0 findings.
- ✅ Mypy strict: 0 errors w 55 plikach.
- ✅ Modern HA API (`entry.runtime_data`, `async_forward_entry_setups`).
- ✅ Scanner split w toku (2.3.4–2.3.9).

---

## Zakres i kolejność

**Grupa A — Dead code (bezpieczne, zero ryzyka):**
1. Fix #1 — Usunięcie 3 osieroconych mixinów scannera (−1312 linii)
2. Fix #2 — Usunięcie `register_addresses.py` (−32 linie)
3. Fix #3 — Usunięcie `validate.yaml` z root (duplikat CI, nieaktywny)
4. Fix #4 — Wywalenie pyflakes z CI (duplikat ruff)

**Grupa B — `_compat.py` cleanup (niskie ryzyko):**
5. Fix #5 — `_compat.py` jako re-export module (−100 linii dead fallbacks)

**Grupa C — Wykorzystanie referencji PDF (feature add):**
6. Fix #6 — Cross-validation `airpack4_modbus.json` ↔ integracja

**Grupa D — Konsolidacje (niskie ryzyko):**
7. Fix #7 — Konsolidacja `scanner_io.py` + `scanner/io.py`

**Grupa E — Production code detox (średnie/wysokie ryzyko, wymaga napraw testów):**
8. Fix #8 — Usunięcie `_update_failed_exception` skanującego `sys.modules`
9. Fix #9 — Usunięcie aliasu `__init__.er` dla test monkey-patchy
10. Fix #10 — Usunięcie `entity_mappings.py` shim
11. Fix #11 — Usunięcie `_async_patch_coordinator_compat` + `_PermissiveCapabilities`
12. Fix #12 — Usunięcie `_SafeDTUtil` defensywny wrapper
13. Fix #13 — Usunięcie `super().__init__()` TypeError fallback
14. Fix #14 — Cleanup `config_flow.py` test-compat warstwy (67× `# pragma: no cover`)
15. Fix #15 — Cleanup `except BaseException` + `__class__.__name__` w `__init__.py`
16. Fix #16 — Audit `async_migrate_entry` (czy v1 jeszcze istnieje?)
17. Fix #17 — Defensywne `getattr` w krytycznych ścieżkach

**Zalecana strategia wdrożenia:**
- **Commit 1:** Fixy #1-#4 (zero ryzyka, CI powinien przejść od razu)
- **Commit 2:** Fix #5 (`_compat.py` cleanup)
- **Commit 3:** Fix #6 (nowa funkcjonalność — cross-validation)
- **Commit 4:** Fix #7 (konsolidacja scannera)
- **Commit 5-14:** Fixy #8-#17 pojedynczo, każdy z naprawą padających testów

Po każdym commicie:
```bash
ruff check custom_components/ tests/ tools/
mypy custom_components/thessla_green_modbus/
pytest tests/ -x -q
```

---

# GRUPA A — Dead code cleanup

## Fix #1 — Usuń 3 osierocone mixiny scannera (1312 linii)

**Pliki do usunięcia:**
- `custom_components/thessla_green_modbus/_scanner_capabilities_mixin.py` (262 linie, 11.6 KB)
- `custom_components/thessla_green_modbus/_scanner_registers_mixin.py` (750 linii, 33 KB)
- `custom_components/thessla_green_modbus/_scanner_transport_mixin.py` (300 linii, 12 KB)

**Razem: 1312 linii / 57 KB martwego kodu.**

**Dowód:**
```bash
grep -rn "_scanner_capabilities_mixin\|_scanner_registers_mixin\|_scanner_transport_mixin\|_ScannerCapabilitiesMixin\|_ScannerRegistersMixin\|_ScannerTransportMixin" \
    custom_components/ tests/ tools/ --include="*.py"
```

Wynik: **tylko self-references wewnątrz samych tych 3 plików**. Powstały jako etap pośredni w refactorze `scanner_core.py` → `scanner/` package (wersje 2.3.4–2.3.9). Po przeniesieniu logiki do `scanner/capabilities.py`, `scanner/registers.py`, `scanner/io.py` — mixiny powinny były zniknąć, ale zostały.

### Krok 1 — usuń 3 pliki

```bash
cd custom_components/thessla_green_modbus
rm _scanner_capabilities_mixin.py
rm _scanner_registers_mixin.py
rm _scanner_transport_mixin.py
```

### Weryfikacja

```bash
grep -rn "_scanner_capabilities_mixin\|_scanner_registers_mixin\|_scanner_transport_mixin" \
    custom_components/ tests/ tools/ --include="*.py"
# Expected: 0 wyników

ruff check custom_components/ tests/ tools/
mypy custom_components/thessla_green_modbus/
pytest tests/ -x -q
```

---

## Fix #2 — Usuń osierocony `register_addresses.py`

**Plik:** `custom_components/thessla_green_modbus/register_addresses.py` (32 linie)

**Dowód:**
```bash
grep -rn "register_addresses\|REG_MIN_PERCENT\|REG_MAX_PERCENT\|REG_ON_OFF_PANEL_MODE\|REG_TEMPORARY_FLOW\|REG_TEMPORARY_TEMP" \
    custom_components/ tests/ tools/ --include="*.py"
```

Wynik: **tylko self-references**. Stałe `REG_MIN_PERCENT = 276`, `REG_MAX_PERCENT = 277`, `REG_ON_OFF_PANEL_MODE = 4387`, `REG_TEMPORARY_FLOW_*`, `REG_TEMPORARY_TEMP_*` — żadna nie jest używana.

### Krok 2 — usuń plik

```bash
rm custom_components/thessla_green_modbus/register_addresses.py
```

### Weryfikacja

```bash
grep -rn "register_addresses\|REG_MIN_PERCENT\|REG_MAX_PERCENT" custom_components/ tests/ tools/ --include="*.py"
# Expected: 0 wyników
```

---

## Fix #3 — Usuń `validate.yaml` z root

**Plik:** `validate.yaml` (w korzeniu repo, 871 bajtów)

**Dowód:**
```bash
ls .github/workflows/
# Wynik: ci.yaml (tylko ten)
```

**GitHub Actions czyta workflows wyłącznie z `.github/workflows/`.** Plik `validate.yaml` w root repo **nigdy się nie wykonuje**. Dodatkowo odwołuje się do `home-assistant/actions/helpers/hacs-validate@master` (archaiczne, bez pinned version) i `vulture` (nieużywany).

### Krok 3 — usuń plik

```bash
rm validate.yaml
```

### Krok 3b — usuń `vulture` z requirements-dev.txt

```bash
grep vulture requirements-dev.txt
# Powinno pokazać: vulture>=2.11,<3.0
```

#### SZUKAJ w `requirements-dev.txt`
```
vulture>=2.11,<3.0
```

#### USUŃ (całą linię)

Wyszukaj też komentarz w `__init__.py`:
```bash
grep -n "vulture" custom_components/thessla_green_modbus/__init__.py
```

Jeśli znajdziesz *"vulture marks it as unused"* — usuń ten komentarz (adres w Fix #16).

---

## Fix #4 — Wywal `pyflakes` z CI (duplikat `ruff`)

**Plik:** `.github/workflows/ci.yaml`

**Dowód:**
```yaml
- name: Ruff (custom_components gate)
  run: ruff check custom_components/

- name: Pyflakes (custom_components)
  run: python -m pyflakes custom_components/
```

`pyproject.toml`:
```toml
[tool.ruff.lint]
select = ["F", "E", "W", "B", "SIM", "RUF", "UP", "I", "PERF", "BLE"]
```

**Reguły `F` w ruff = Pyflakes.** CHANGELOG v2.3.1 zapowiadał *"Replaced pyflakes with ruff as the primary linter"* — ale step pozostał.

### Krok 4 — usuń step

**Plik:** `.github/workflows/ci.yaml`

#### SZUKAJ
```yaml
      - name: Ruff (custom_components gate)
        run: ruff check custom_components/

      - name: Pyflakes (custom_components)
        run: python -m pyflakes custom_components/

      - name: Ruff (repo)
        run: ruff check .
```

#### ZASTĄP
```yaml
      - name: Ruff
        run: ruff check .
```

(Uprościłem też dwa kroki ruff w jeden — `ruff check .` obejmuje `custom_components/`.)

---

# GRUPA B — `_compat.py` cleanup

## Fix #5 — Przepisz `_compat.py` jako czyste re-exports

**Plik:** `custom_components/thessla_green_modbus/_compat.py` (144 linie → ~40 linii)

**Kontekst:**
Plik zawiera 8 bloków `try/except ImportError` służących do uruchamiania kodu w środowisku bez Home Assistant. Ale manifest wymaga `"homeassistant": "2026.1.0"` i `python>=3.13`, więc te fallbacki są dead paths.

**Analiza każdego fallbacku:**

| Symbol | Decyzja |
|---|---|
| `UTC = getattr(dt, "UTC", ...)` + `# noqa: UP017` | **USUŃ** — py3.13 ma `datetime.UTC`. |
| `dt_util` z `_DTUtil` fallback | **USUŃ fallback, zostaw re-export** — `homeassistant.util.dt` zawsze dostępne w HA. |
| `BinarySensorDeviceClass` fallback | **USUŃ** — w HA od 2021. |
| `SensorDeviceClass` / `SensorStateClass` fallback | **USUŃ** — w HA od 2022. |
| `EntityCategory` fallback | **USUŃ** — w HA od 2022. |
| `DeviceInfo` fallback | **USUŃ** — w HA od 2022. |
| `EVENT_HOMEASSISTANT_STOP` fallback | **USUŃ** — core constant. |
| `PERCENTAGE`, `UnitOf*` fallback | **USUŃ** — core constants. |
| `DataUpdateCoordinator`, `UpdateFailed` fallback | **USUŃ** — jeśli nie ma HA, coordinator i tak nie działa. |
| `COORDINATOR_BASE = DataUpdateCoordinator[...]` + `TypeError` catch | **USUŃ** — HA 2026.1.0 zawsze wspiera generic. |

### Krok 5 — przepisz `_compat.py`

#### ZASTĄP cały plik `custom_components/thessla_green_modbus/_compat.py`

```python
"""Compatibility re-exports for Home Assistant symbols used across the integration.

Historically this module provided fallbacks for running integration code without
a full Home Assistant install. Since manifest.json requires homeassistant>=2026.1.0
and requires-python>=3.13, all fallbacks have been removed. This module now only
re-exports symbols from HA so the rest of the integration has a single import point.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

COORDINATOR_BASE = DataUpdateCoordinator[dict[str, Any]]

__all__ = [
    "COORDINATOR_BASE",
    "BinarySensorDeviceClass",
    "DataUpdateCoordinator",
    "DeviceInfo",
    "EVENT_HOMEASSISTANT_STOP",
    "EntityCategory",
    "PERCENTAGE",
    "SensorDeviceClass",
    "SensorStateClass",
    "UTC",
    "UnitOfElectricPotential",
    "UnitOfPower",
    "UnitOfTemperature",
    "UnitOfTime",
    "UnitOfVolumeFlowRate",
    "UpdateFailed",
    "dt_util",
]
```

### Uwaga

Zostawiamy `_compat.py` jako moduł, bo jest importowany z 8+ miejsc. Jedyna zmiana — usuwamy `try/except ImportError` gałęzie które były martwe.

### Weryfikacja

```bash
mypy custom_components/thessla_green_modbus/
ruff check custom_components/ tests/ tools/
pytest tests/ -x -q
```

---

# GRUPA C — Wykorzystanie referencji PDF

## Fix #6 — Cross-validate `airpack4_modbus.json` z integracją

**Kontekst:** `airpack4_modbus.json` (91 KB w root) jest wygenerowany z PDF producenta i służy jako referencyjne źródło prawdy. Ale **nikt tego nie używa** — plik leży niewykorzystany.

**Ad-hoc analiza rozbieżności:**
```
REF (vendor PDF → JSON):     294 rejestrów
MAIN (integracja):           356 rejestrów

COMMON:                      294
Brakuje w integracji:          0  ✅
Extra w integracji:           62  (23 bitmap bits + 37 error codes + 2 realne extras)
Różnice w nazwach:           242  (część legit renames, część warte weryfikacji)
```

**62 extra rejestry w integracji:**
- 23× `s_N` (np. `s_2`, `s_6`, `s_9`) — pseudorrejestry-bity dekodowane z rejestru bitmap alarmów 0x2000.
- 37× `alarm`, `error`, `e_99`..`e_252`, `f_142`..`f_147`, `e_196_e_199` — pseudorrejestry dla bitmap błędów.
- 2× rzeczywiście brakujących w REF — **warte weryfikacji z producentem**:
  - `FC04 0x0017` — `heating_temperature` (TH sensor)
  - `FC04 0x012A` — `water_removal_active` (HEWR procedure)

### Krok 6a — dodaj skrypt porównujący

**Plik:** `tools/compare_registers_with_reference.py` (NOWY)

```python
#!/usr/bin/env python3
"""Compare integration register JSON with the vendor reference (airpack4_modbus.json).

The reference file is generated from the manufacturer PDF and serves as the
source of truth for addresses and Modbus function codes. This tool reports:

1. Registers in the reference that are missing from the integration.
2. Registers in the integration that are extra (not in reference).
3. Name mismatches on common (function, address) pairs.

By default the script exits non-zero if there are unexpected discrepancies.
Use --allow-extra to permit integration-specific pseudo-registers (bitmap bits,
synthetic entities). See ``KNOWN_EXTRA_PREFIXES`` for the current allowlist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "airpack4_modbus.json"
MAIN_PATH = (
    ROOT / "custom_components" / "thessla_green_modbus" / "registers"
    / "thessla_green_registers_full.json"
)

# Integration-specific pseudo-registers (decoded from bitmap registers in the
# device). These are intentionally absent from the vendor reference.
KNOWN_EXTRA_PREFIXES = (
    "alarm",
    "error",
    "s_",      # alarm bits decoded from 0x2000 bitmap
    "e_",      # error bits decoded from 0x2001+ bitmaps
    "f_",      # filter-related flag bits
)


def _fc_num(key: str) -> int:
    """'fc03_holding_registers' -> 3"""
    return int(key[2:4])


def _load_reference() -> dict[tuple[int, int], dict]:
    """Return {(function, address): entry} from vendor reference."""
    data = json.loads(REF_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for key in (
        "fc01_coils",
        "fc02_discrete_inputs",
        "fc03_holding_registers",
        "fc04_input_registers",
    ):
        fn = _fc_num(key)
        for entry in data[key]["registers"]:
            addr = entry.get("dec")
            if addr is None:
                addr = int(entry["hex"], 16)
            result[(fn, int(addr))] = entry
    return result


def _load_main() -> dict[tuple[int, int], dict]:
    """Return {(function, address): entry} from integration JSON."""
    data = json.loads(MAIN_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for r in data["registers"]:
        fn = int(str(r["function"]))
        addr = r.get("address_dec")
        if addr is None:
            addr = int(str(r["address_hex"]), 16)
        result[(fn, int(addr))] = r
    return result


def _is_known_extra(entry: dict) -> bool:
    name = entry.get("name") or ""
    return any(name.startswith(p) for p in KNOWN_EXTRA_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on any name mismatch (even for known-safe renames).",
    )
    parser.add_argument(
        "--show-renames",
        action="store_true",
        help="Print every name mismatch, not just summary.",
    )
    args = parser.parse_args()

    ref = _load_reference()
    main = _load_main()

    only_ref = set(ref) - set(main)
    only_main = set(main) - set(ref)
    common = set(ref) & set(main)

    print(f"Reference entries: {len(ref)}")
    print(f"Integration entries: {len(main)}")
    print(f"Common: {len(common)}")
    print(f"Missing from integration: {len(only_ref)}")
    print(f"Extra in integration: {len(only_main)}")

    errors = 0

    if only_ref:
        print("\n!! MISSING from integration (this is a bug) !!")
        for p in sorted(only_ref):
            e = ref[p]
            print(f"  FC{p[0]:02d} 0x{p[1]:04X} ({p[1]:5d}): {e.get('name')!r}")
        errors += len(only_ref)

    unexpected_extra = [p for p in only_main if not _is_known_extra(main[p])]
    if unexpected_extra:
        print("\n?? UNEXPECTED extras in integration (verify with vendor) ??")
        for p in sorted(unexpected_extra):
            e = main[p]
            print(f"  FC{p[0]:02d} 0x{p[1]:04X} ({p[1]:5d}): {e.get('name')!r}")
            print(f"    {str(e.get('description'))[:100]}")
        if args.strict:
            errors += len(unexpected_extra)

    mismatches = []
    for p in common:
        rn = ref[p].get("name")
        mn = main[p].get("name")
        if rn and mn and rn != mn:
            mismatches.append((p, rn, mn))

    print(f"\nName mismatches on common addresses: {len(mismatches)}")
    if args.show_renames:
        for p, rn, mn in sorted(mismatches):
            print(f"  FC{p[0]:02d} 0x{p[1]:04X}: ref={rn!r:45s} -> main={mn!r}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

### Krok 6b — dodaj test cross-validation

**Plik:** `tests/test_registers_vs_reference.py` (NOWY)

```python
"""Verify integration registers match the vendor reference (airpack4_modbus.json)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "airpack4_modbus.json"
MAIN_PATH = (
    ROOT / "custom_components" / "thessla_green_modbus" / "registers"
    / "thessla_green_registers_full.json"
)

KNOWN_EXTRA_PREFIXES = ("alarm", "error", "s_", "e_", "f_")

# Non-bitmap extras that need separate justification.
KNOWN_EXTRA_WHITELIST = {
    # (function, address): "justification"
    (4, 0x0017): "heating_temperature TH sensor, present on AirPack4 h/v units",
    (4, 0x012A): "water_removal_active HEWR procedure flag, series 4",
}


def _fc_num(key: str) -> int:
    return int(key[2:4])


@pytest.fixture(scope="module")
def reference_pairs() -> dict[tuple[int, int], dict]:
    data = json.loads(REF_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for key in (
        "fc01_coils",
        "fc02_discrete_inputs",
        "fc03_holding_registers",
        "fc04_input_registers",
    ):
        fn = _fc_num(key)
        for entry in data[key]["registers"]:
            addr = entry.get("dec")
            if addr is None:
                addr = int(entry["hex"], 16)
            result[(fn, int(addr))] = entry
    return result


@pytest.fixture(scope="module")
def main_pairs() -> dict[tuple[int, int], dict]:
    data = json.loads(MAIN_PATH.read_text(encoding="utf-8"))
    result: dict[tuple[int, int], dict] = {}
    for r in data["registers"]:
        fn = int(str(r["function"]))
        addr = r.get("address_dec")
        if addr is None:
            addr = int(str(r["address_hex"]), 16)
        result[(fn, int(addr))] = r
    return result


def test_all_reference_registers_present(reference_pairs, main_pairs):
    """Every (function, address) pair in vendor reference must exist in integration JSON."""
    missing = set(reference_pairs) - set(main_pairs)
    assert not missing, (
        f"Registers in vendor reference but missing from integration: "
        f"{sorted(missing)}"
    )


def test_extras_are_known(reference_pairs, main_pairs):
    """Integration may have extras, but they must be either decoded bitmap bits
    or explicitly whitelisted."""
    extras = set(main_pairs) - set(reference_pairs)
    unknown_extras = []
    for pair in extras:
        entry = main_pairs[pair]
        name = entry.get("name") or ""
        if any(name.startswith(p) for p in KNOWN_EXTRA_PREFIXES):
            continue
        if pair in KNOWN_EXTRA_WHITELIST:
            continue
        unknown_extras.append((pair, name))

    assert not unknown_extras, (
        f"Integration has registers not in reference and not whitelisted: "
        f"{unknown_extras}. Either add to KNOWN_EXTRA_WHITELIST with justification "
        f"or remove from integration."
    )
```

### Krok 6c — dodaj step do CI

**Plik:** `.github/workflows/ci.yaml` — w sekcji `lint` po ruff:

```yaml
      - name: Compare registers with vendor reference
        run: python tools/compare_registers_with_reference.py
```

---

# GRUPA D — Konsolidacje

## Fix #7 — Konsolidacja `scanner_io.py` + `scanner/io.py`

**Pliki:**
- `custom_components/thessla_green_modbus/scanner_io.py` (~90 linii, utility)
- `custom_components/thessla_green_modbus/scanner/io.py` (548 linii, nowa struktura)

**Dowód problemu:**

`scanner_io.py:11`:
```python
def is_request_cancelled_error(exc: Exception) -> bool:
    """Return ``True`` when an exception indicates a cancelled Modbus request."""
    message = str(exc).lower()
    return "request cancelled outside pymodbus" in message or "cancelled" in message
```

`scanner/io.py:25`:
```python
def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    return bool(_scanner_io.is_request_cancelled_error(exc))
```

Drugi to thin-wrapper na pierwszy. Czterech użytkowników, część importuje `.scanner_io`, część `.scanner.io`.

### Krok 7a — przenieś definicję do `scanner/io.py`

**Plik:** `custom_components/thessla_green_modbus/scanner/io.py`

#### SZUKAJ
```python
from .. import scanner_io as _scanner_io
```

#### USUŃ tę linię

#### SZUKAJ (linia 25)
```python
def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    return bool(_scanner_io.is_request_cancelled_error(exc))
```

#### ZASTĄP
```python
def is_request_cancelled_error(exc: Exception) -> bool:
    """Return True when an exception indicates a cancelled Modbus request."""
    message = str(exc).lower()
    return "request cancelled outside pymodbus" in message or "cancelled" in message
```

### Krok 7b — `scanner_io.py` staje się re-export shim

**Plik:** `custom_components/thessla_green_modbus/scanner_io.py`

#### ZASTĄP całą zawartość
```python
"""Backward compatibility shim — scanner I/O helpers.

The original module content has moved to :mod:`scanner.io`. This shim
re-exports the public helpers for callers that import the old path.
"""

from __future__ import annotations

from .scanner.io import is_request_cancelled_error

__all__ = ["is_request_cancelled_error"]
```

**Uwaga:** sprawdź czy `ensure_pymodbus_client_module` (obecna w `scanner_io.py`) jest używana gdzieś. Jeśli tak — przenieś ją też do `scanner/io.py` i dodaj do re-exportu.

```bash
grep -rn "ensure_pymodbus_client_module" custom_components/ tests/ --include="*.py"
```

---

# GRUPA E — Production code detox

**WAŻNE:** Fixy #8-#17 mogą powodować padanie testów. **Każdy padający test to sygnał** że test opierał się na produkcyjnym smell'u. Napraw test (używając `pytest-homeassistant-custom-component` który jest w deps), nie cofaj zmiany w produkcji.

---

## Fix #8 — Usuń `_update_failed_exception` skanujące `sys.modules`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód (linie 134-148):**
```python
def _update_failed_exception(message: str) -> Exception:
    """Return an UpdateFailed compatible with patched test helper modules."""

    classes: list[type[Exception]] = [UpdateFailed]
    for mod_name in ("tests.conftest", "tests.test_coordinator", "tests.test_services"):
        mod = sys.modules.get(mod_name)
        cls = getattr(mod, "UpdateFailed", None) if mod is not None else None
        if isinstance(cls, type) and issubclass(cls, Exception) and cls not in classes:
            classes.append(cls)

    if len(classes) == 1:
        return classes[0](message)  # pragma: no cover

    compat_cls = cast(type[Exception], type("CompatUpdateFailed", tuple(classes), {}))
    return compat_cls(message)
```

**Co to robi:** produkcja szuka `tests/conftest.py`, `tests/test_coordinator.py`, `tests/test_services.py` w `sys.modules`. Jeśli któryś zdefiniował własną klasę `UpdateFailed`, produkcja tworzy dynamicznie klasę dziedziczącą po wszystkich. **Coordinator zna nazwy plików testowych**.

### Krok 8a — usuń funkcję

#### SZUKAJ (linie 134-148)
```python
def _update_failed_exception(message: str) -> Exception:
    """Return an UpdateFailed compatible with patched test helper modules."""

    classes: list[type[Exception]] = [UpdateFailed]
    for mod_name in ("tests.conftest", "tests.test_coordinator", "tests.test_services"):
        mod = sys.modules.get(mod_name)
        cls = getattr(mod, "UpdateFailed", None) if mod is not None else None
        if isinstance(cls, type) and issubclass(cls, Exception) and cls not in classes:
            classes.append(cls)

    if len(classes) == 1:
        return classes[0](message)  # pragma: no cover

    compat_cls = cast(type[Exception], type("CompatUpdateFailed", tuple(classes), {}))
    return compat_cls(message)
```

#### USUŃ (całość)

### Krok 8b — zastąp wszystkie wywołania

```bash
grep -rn "_update_failed_exception" custom_components/ tests/ --include="*.py"
```

W każdym miejscu zastąp `_update_failed_exception(msg)` → `UpdateFailed(msg)`.

### Krok 8c — usuń nieużywane importy

```bash
grep -n "cast\|import sys" custom_components/thessla_green_modbus/coordinator.py
```

Jeśli `cast` i `sys` są używane tylko w usuniętej funkcji — usuń ich importy.

### Krok 8d — napraw testy

```bash
grep -rn "class UpdateFailed\|UpdateFailed = " tests/ --include="*.py"
```

Każdy taki test przepisz używając:
```python
from homeassistant.helpers.update_coordinator import UpdateFailed
```

---

## Fix #9 — Usuń alias `__init__.er` dla testów

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 87-92):**
```python
# Compatibility shim for tests patching "custom_components.thessla_green_modbus.__init__.er".
_init_alias = sys.modules.setdefault(f"{__name__}.__init__", sys.modules[__name__])
_init_alias_any: Any = _init_alias
_init_alias_any.er = er
module_self: Any = sys.modules[__name__]
module_self.__init__ = _init_alias
```

Produkcja rejestruje w `sys.modules` fikcyjny moduł `custom_components.thessla_green_modbus.__init__`, żeby testy mogły robić `monkeypatch.setattr("custom_components.thessla_green_modbus.__init__.er", ...)`.

### Krok 9a — usuń alias

#### SZUKAJ (linie 87-92)
```python
# Compatibility shim for tests patching "custom_components.thessla_green_modbus.__init__.er".
_init_alias = sys.modules.setdefault(f"{__name__}.__init__", sys.modules[__name__])
_init_alias_any: Any = _init_alias
_init_alias_any.er = er
module_self: Any = sys.modules[__name__]
module_self.__init__ = _init_alias
```

#### USUŃ (całość)

### Krok 9b — napraw testy

```bash
grep -rn "thessla_green_modbus\.__init__\.\|__init__\.er\b" tests/ --include="*.py"
```

Dla każdego znalezionego `monkeypatch.setattr("...__init__.er", ...)` zmień na:
```python
monkeypatch.setattr("custom_components.thessla_green_modbus.er", ...)
```

---

## Fix #10 — Usuń `entity_mappings.py` shim

**Plik:** `custom_components/thessla_green_modbus/entity_mappings.py` (37 linii)

**Dowód:**
```python
"""Backward-compatible shim for the ``mappings`` package."""
# ...
# Keep ``entity_mappings`` as an alias of ``mappings`` so existing tests and
# monkeypatches that mutate module globals continue to affect runtime behavior.
_m.__file__ = __file__
sys.modules[__name__] = _m
```

### Krok 10a — zamień wszystkie importy

Miejsca do zmiany:
```
register_map.py:173     from .entity_mappings import ENTITY_MAPPINGS
switch.py:19            from .entity_mappings import ENTITY_MAPPINGS
__init__.py:72          from .entity_mappings import async_setup_entity_mappings
const.py:309            from .entity_mappings import ENTITY_MAPPINGS as _MAP
number.py:19            from .entity_mappings import ENTITY_MAPPINGS
time.py:23              from .entity_mappings import ENTITY_MAPPINGS
sensor.py:34            from .entity_mappings import ENTITY_MAPPINGS
binary_sensor.py:26     from .entity_mappings import BINARY_SENSOR_ENTITY_MAPPINGS
text.py:22              from .entity_mappings import ENTITY_MAPPINGS
services.py:32          from .entity_mappings import map_legacy_entity_id
```

**W każdym pliku zamień:** `from .entity_mappings import X` → `from .mappings import X`

### Krok 10b — usuń plik

```bash
rm custom_components/thessla_green_modbus/entity_mappings.py
```

### Krok 10c — napraw testy

```bash
grep -rn "entity_mappings\b" tests/ --include="*.py"
```

Zmień `entity_mappings` → `mappings` w testach.

---

## Fix #11 — Usuń `_async_patch_coordinator_compat` + `_PermissiveCapabilities`

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 384-415):**
```python
def _async_patch_coordinator_compat(coordinator, entry):  # pragma: no cover
    """Add lightweight fallback attributes for test environments."""
    if not hasattr(coordinator, "capabilities"):

        class _PermissiveCapabilities:
            def __getattr__(self, _name: str) -> bool:
                return True

        coordinator.capabilities = _PermissiveCapabilities()

    if not hasattr(coordinator, "get_register_map"):
        # ... dorabia empty register maps
    if not hasattr(coordinator, "available_registers"):
        # ... dorabia empty sets
    if not hasattr(coordinator, "force_full_register_list"):
        # ...
```

**Co to robi:** `_PermissiveCapabilities` zwraca `True` dla każdego atrybutu — *"urządzenie ma każdą funkcję"*. **Wywoływane w każdym setupie**, nie tylko testowym (linia 475).

### Krok 11a — usuń funkcję

#### SZUKAJ (linie 384-415) - funkcja `_async_patch_coordinator_compat` w całości

#### USUŃ

### Krok 11b — usuń wywołanie

```bash
grep -n "_async_patch_coordinator_compat" custom_components/thessla_green_modbus/__init__.py
```

Usuń wywołanie (linia ~475).

### Krok 11c — napraw testy

Jeśli testy polegają na `_PermissiveCapabilities` (SimpleNamespace bez capabilities):

```python
# Źle:
coordinator = SimpleNamespace(host="1.2.3.4", port=502)

# Dobrze:
coordinator = MagicMock(spec=ThesslaGreenModbusCoordinator)
coordinator.capabilities.basic_control = True
coordinator.available_registers = {...}
```

---

## Fix #12 — Usuń `_SafeDTUtil` defensywny wrapper

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód (linie 84-119):**
```python
class _SafeDTUtil:
    """Wrap dt helpers and always return timezone-aware datetimes."""
    # ... defensywnie sprawdza czy base ma now/utcnow, czy są callable, 
    # czy zwracają datetime, czy mają tzinfo

def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    utcnow_callable = getattr(dt_util, "utcnow", None)
    # ... jeszcze raz te same sprawdzenia
```

HA `dt_util.utcnow()` zawsze zwraca `datetime` z `tzinfo=UTC`. Gwarancja od 2022.

### Krok 12 — uprość

#### SZUKAJ (linie 84-119)
```python
class _SafeDTUtil:
    """Wrap dt helpers and always return timezone-aware datetimes."""

    def __init__(self, base: Any) -> None:
        self._base = base

    @staticmethod
    def _coerce(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return datetime.now(UTC)

    def now(self) -> datetime:
        func = getattr(self._base, "now", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)

    def utcnow(self) -> datetime:
        func = getattr(self._base, "utcnow", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)


dt_util = _SafeDTUtil(_base_dt_util)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    utcnow_callable = getattr(dt_util, "utcnow", None)
    if callable(utcnow_callable):
        value = utcnow_callable()
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return datetime.now(UTC)
```

#### ZASTĄP
```python
# Re-export HA dt util directly. _base_dt_util is imported from ._compat.
dt_util = _base_dt_util


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return dt_util.utcnow()
```

### Napraw testy

Testy mockujące `dt_util.utcnow = lambda: "2024-01-01"` (string zamiast datetime):
```python
# Użyj freezegun:
from freezegun import freeze_time

@freeze_time("2024-01-01 12:00:00")
def test_something():
    ...
```

---

## Fix #13 — Usuń `super().__init__()` TypeError fallback

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód (linie 195-207):**
```python
try:
    super().__init__(
        hass, _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id if entry else name}",
        update_interval=update_interval,
    )
except TypeError:
    super().__init__()
    self.hass = hass
    self.logger = _LOGGER
    self.name = f"{DOMAIN}_{entry.entry_id if entry else name}"
    self.update_interval = update_interval
```

HA `DataUpdateCoordinator.__init__` to stabilne API. `TypeError` path jest dla stubów.

### Krok 13 — usuń fallback

#### SZUKAJ
```python
        try:
            super().__init__(
                hass,
                _LOGGER,
                name=f"{DOMAIN}_{entry.entry_id if entry else name}",
                update_interval=update_interval,
            )
        except TypeError:
            super().__init__()
            self.hass = hass
            self.logger = _LOGGER
            self.name = f"{DOMAIN}_{entry.entry_id if entry else name}"
            self.update_interval = update_interval
```

#### ZASTĄP
```python
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id if entry else name}",
            update_interval=update_interval,
        )
```

---

## Fix #14 — Cleanup `config_flow.py` test-compat warstwy

**Plik:** `custom_components/thessla_green_modbus/config_flow.py`

**Kontekst:** 67× `# pragma: no cover` w jednym pliku. Większość na test-compat shimach.

### Fix #14a — Usuń `DhcpServiceInfo` / `ZeroconfServiceInfo` fallback

#### SZUKAJ (linie 20-43)
```python
if TYPE_CHECKING:
    from homeassistant.components.dhcp import DhcpServiceInfo
    from homeassistant.components.zeroconf import ZeroconfServiceInfo
else:
    try:  # pragma: no cover - optional HA component
        from homeassistant.components.dhcp import DhcpServiceInfo
    except (ImportError, ModuleNotFoundError):  # pragma: no cover

        @dataclasses.dataclass
        class DhcpServiceInfo:  # pragma: no cover
            """Fallback DHCP service info for minimal test environments."""
            macaddress: str | None = None
            ip: str | None = None

    try:  # pragma: no cover - optional HA component
        from homeassistant.components.zeroconf import ZeroconfServiceInfo
    except (ImportError, ModuleNotFoundError):  # pragma: no cover

        @dataclasses.dataclass
        class ZeroconfServiceInfo:  # pragma: no cover
            """Fallback Zeroconf service info for minimal test environments."""
            host: str | None = None
```

#### ZASTĄP
```python
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.zeroconf import ZeroconfServiceInfo
```

### Fix #14b — Usuń `ConfigFlowResult` fallback

#### SZUKAJ (linie 46-49)
```python
try:  # pragma: no cover - available since HA 2023.9
    from homeassistant.config_entries import ConfigFlowResult
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    ConfigFlowResult = dict[str, Any]
```

#### ZASTĄP
```python
from homeassistant.config_entries import ConfigFlowResult
```

### Fix #14c — Usuń `_FallbackFlowBase`

Najpierw sprawdź czy nieużywana:
```bash
grep -n "_FallbackFlowBase" custom_components/thessla_green_modbus/config_flow.py
```

#### SZUKAJ (linie 123-142) - klasa `_FallbackFlowBase` w całości

#### USUŃ (klasa w całości, prawdopodobnie nieużywana)

### Fix #14d — Usuń monkey-patch voluptuous

#### SZUKAJ (linie 175-186)
```python
class _VolInvalid(Exception):
    """Fallback voluptuous Invalid-like exception."""

    def __init__(self, error_message: str, path: list[str] | None = None) -> None:
        super().__init__(error_message)
        self.error_message = error_message
        self.path = path or []


VOL_INVALID = getattr(vol, "Invalid", _VolInvalid)
if not hasattr(vol, "Invalid"):
    vol.Invalid = VOL_INVALID  # pragma: no cover
```

#### ZASTĄP
```python
from voluptuous import Invalid as VOL_INVALID
```

### Fix #14e — Uprość `_schema`

#### SZUKAJ (linie 189-194)
```python
def _schema(definition: Any) -> Any:
    """Create voluptuous schema with `.schema` compatibility for tests."""
    schema_obj = vol.Schema(definition)
    if not hasattr(schema_obj, "schema"):
        schema_obj.schema = definition  # pragma: no cover
    return schema_obj
```

#### ZASTĄP
```python
def _schema(definition: Any) -> vol.Schema:
    return vol.Schema(definition)
```

### Fix #14f — Uprość `_required`

#### SZUKAJ (linie 197-213)
```python
def _required(schema: Any, **kwargs: Any) -> Any:
    """Compat wrapper for voluptuous.Required across test stubs."""
    try:
        return vol.Required(schema, **kwargs)
    except TypeError:  # pragma: no cover
        msg = kwargs.get("msg")  # pragma: no cover
        default = kwargs.get("default", ...)  # pragma: no cover
        description = kwargs.get("description")  # pragma: no cover
        try:  # pragma: no cover
            return vol.Required(schema, msg, default, description)  # pragma: no cover
        except TypeError:  # pragma: no cover
            if default is not ...:  # pragma: no cover
                try:  # pragma: no cover
                    return vol.Required(schema, default=default)  # pragma: no cover
                except TypeError:  # pragma: no cover
                    return vol.Required(schema)  # pragma: no cover
            return vol.Required(schema)  # pragma: no cover
```

#### ZASTĄP
```python
def _required(schema: Any, **kwargs: Any) -> vol.Required:
    return vol.Required(schema, **kwargs)
```

**Lub jeszcze lepiej** — jeśli `_required` wywoływane tylko kilka razy, zamień wywołania na `vol.Required(...)` bezpośrednio:
```bash
grep -n "_required(" custom_components/thessla_green_modbus/config_flow.py
```

---

## Fix #15 — Usuń `except BaseException` + `__class__.__name__` w `__init__.py`

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 322-338 i 363-379, dwa identyczne bloki):**
```python
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt | SystemExit | asyncio.CancelledError):
            raise
        # Deliberately broad at integration setup boundary...
        if (
            isinstance(exc, Exception)
            and (isinstance(exc, UpdateFailed) or exc.__class__.__name__ == "UpdateFailed")
            and is_invalid_auth_error(exc)
        ):
            # ...
```

**Smelle:**
1. `except BaseException` zamiast `except Exception` (potem ręcznie wyklucza SystemExit/KeyboardInterrupt/CancelledError).
2. `exc.__class__.__name__ == "UpdateFailed"` — **porównanie klasy po nazwie stringa**. Po Fix #8 (`_update_failed_exception` usunięte) ten warunek jest bezsensowny.

### Krok 15 — uprość oba bloki

#### SZUKAJ (pierwszy blok, linia 322)
```python
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt | SystemExit | asyncio.CancelledError):
            raise
        # Deliberately broad at integration setup boundary: Home Assistant test
        # stubs and custom coordinator implementations may raise dynamic
        # exception classes (including test-local subclasses of UpdateFailed).
        # We convert all such failures into ConfigEntryNotReady/reauth flow.
        if (
            isinstance(exc, Exception)
            and (isinstance(exc, UpdateFailed) or exc.__class__.__name__ == "UpdateFailed")
            and is_invalid_auth_error(exc)
        ):
            _LOGGER.error("Authentication failed during setup: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc
```

#### ZASTĄP
```python
    except Exception as exc:
        if isinstance(exc, UpdateFailed) and is_invalid_auth_error(exc):
            _LOGGER.error("Authentication failed during setup: %s", exc)
            await entry.async_start_reauth(hass)
            return False
        _LOGGER.error("Failed to setup coordinator: %s", exc)
        raise ConfigEntryNotReady(f"Unable to connect to device: {exc}") from exc
```

**Zrób analogicznie z drugim blokiem (linia 363).**

`except Exception` automatycznie wyłącza `KeyboardInterrupt`, `SystemExit`, `CancelledError` (dziedziczą z `BaseException`, nie `Exception`).

---

## Fix #16 — Audit `async_migrate_entry` (czy v1 jeszcze istnieje?)

**Plik:** `custom_components/thessla_green_modbus/__init__.py`

**Dowód (linie 1052+):**
```python
async def async_migrate_entry(hass, config_entry) -> bool:
    """Migrate old entry.

    Home Assistant uses this during upgrades; vulture marks it as unused but
    the runtime imports it dynamically.
    """
    if config_entry.version == 1:
        # ... migrate "unit" to CONF_SLAVE_ID, add CONF_PORT=8899, etc.
```

**Pytania:**
1. Czy ktoś jeszcze używa `config_entry.version == 1`? (config z pre-2.x).
2. Komentarz o vulture — Fix #3 usuwa vulture, komentarz staje się bezsensowny.

### Krok 16a — zaktualizuj komentarz

#### SZUKAJ
```python
async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:  # pragma: no cover
    """Migrate old entry.

    Home Assistant uses this during upgrades; vulture marks it as unused but
    the runtime imports it dynamically.
    """
```

#### ZASTĄP
```python
async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:  # pragma: no cover
    """Migrate old entry.

    Called by Home Assistant during integration upgrades.
    """
```

### Krok 16b — opcjonalne: usuń gałąź v1 (decyzja biznesowa)

Jeśli Bart zgadza się że po 2+ latach użytkownicy powinni być na v2+:

#### SZUKAJ
```python
    if config_entry.version == 1:
        # Migrate "unit" to CONF_SLAVE_ID if needed
        if "unit" in new_data and CONF_SLAVE_ID not in new_data:
            new_data[CONF_SLAVE_ID] = new_data["unit"]
            _LOGGER.info("Migrated 'unit' to '%s'", CONF_SLAVE_ID)

        # Ensure port is present; older versions relied on legacy default
        if CONF_PORT not in new_data:
            new_data[CONF_PORT] = LEGACY_DEFAULT_PORT
            _LOGGER.info("Added '%s' with legacy default %s", CONF_PORT, LEGACY_DEFAULT_PORT)

        # Add new fields with defaults if missing
        if CONF_SCAN_INTERVAL not in new_options:
            new_options[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        if CONF_TIMEOUT not in new_options:
            new_options[CONF_TIMEOUT] = DEFAULT_TIMEOUT
        if CONF_RETRY not in new_options:
            new_options[CONF_RETRY] = DEFAULT_RETRY
        if CONF_FORCE_FULL_REGISTER_LIST not in new_options:
            new_options[CONF_FORCE_FULL_REGISTER_LIST] = False

        config_entry.version = 2
```

#### USUŃ blok i `LEGACY_DEFAULT_PORT = 8899` z góry pliku

**Użytkownicy na pre-v2 będą musieli usunąć i ponownie dodać integrację.** Decyzja biznesowa — można zostawić.

---

## Fix #17 — Defensywne `getattr` w krytycznych ścieżkach

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód (linia 413):**
```python
start_reauth = getattr(self.entry, "async_start_reauth", None)
```

HA ConfigEntry ma `async_start_reauth` od 2023. Defensywny `getattr` istnieje tylko dla SimpleNamespace testów.

### Krok 17a — cleanup `async_start_reauth`

```bash
grep -n "async_start_reauth" custom_components/thessla_green_modbus/coordinator.py
```

#### SZUKAJ (wzorzec podobny do poniższego)
```python
        start_reauth = getattr(self.entry, "async_start_reauth", None)
        if callable(start_reauth):
            # ... wywołanie
```

#### ZASTĄP
```python
        if self.entry is not None:
            self.entry.async_start_reauth(self.hass)
```

### Krok 17b — audit pozostałych getattr

```bash
grep -rn "getattr(.*, None)" custom_components/thessla_green_modbus/ --include="*.py" | \
    grep -v "scanner\|mappings\|_loaders"
```

Dla każdego wystąpienia:
- Czy docelowy atrybut istnieje w prawdziwym HA / PyModbus / voluptuous?
- Jeśli tak → `getattr` to smell, usunąć.
- Jeśli nie (np. optional component, dynamic method lookup) → zostawić z komentarzem dlaczego.

**Nie zmieniać:**
- `getattr(client, name, None) if client is not None else None` w `_get_client_method` (coordinator.py:435) — uzasadnione, różne klienty Modbus mają różne metody.
- `getattr(response, "exception_code", None)` w scanner/io.py:186 — pymodbus response może nie mieć tego pola.

---

# Weryfikacja końcowa

Po zastosowaniu Fixów #1-#17:

```bash
# Baseline:
ruff check custom_components/ tests/ tools/     # Expected: "All checks passed!"
mypy custom_components/thessla_green_modbus/    # Expected: "Success: no issues found in ~48 source files"
                                                 # (−4 pliki: 3 mixiny + register_addresses + entity_mappings)

# Testy — tutaj prawdopodobnie część będzie padać po Grupie E:
pytest tests/ -x -q
```

**Co robić z padającymi testami po Grupie E:**

1. **Test używa SimpleNamespace zamiast HA Mock** → przepisz test na `MagicMock(spec=ThesslaGreenModbusCoordinator)` albo `pytest-homeassistant-custom-component`.
2. **Test definiuje własny UpdateFailed** → użyj `from homeassistant.helpers.update_coordinator import UpdateFailed`.
3. **Test patchuje `voluptuous.Invalid`** → użyj prawdziwego voluptuous (już w deps).
4. **Test mockuje `dt_util.utcnow = lambda: "2024-01-01"` (string)** → użyj `freezegun` albo prawdziwego `datetime`.
5. **Test używa `entity_mappings` zamiast `mappings`** → zmień import.

**Nowy test:**
```bash
# Po Fix #6:
python tools/compare_registers_with_reference.py
# Expected: 0 exit code (tylko name mismatches, bez missing/unexpected)
```

**Metryki docelowe:**

```
                                  v2.3.9       v2.4.0 (target)
Pliki .py w custom_components:     55           48           (−7)
Linie produkcji:                  ~14500       ~12800-13200  (−1400 do −1700)
_compat.py:                        144          ~40           (−100)
Test-compat code:                 ~400          ~0
sys.modules hacks:                   4            1 (tylko scanner_core.py shim)
# pragma: no cover w config_flow:   67          ~15
Klasy/funkcje tylko dla testów:     ~8           0
Test suite pass rate:              ~100%        po napraw testów: 100%
```

---

## Bump wersji i CHANGELOG

**Plik:** `custom_components/thessla_green_modbus/manifest.json`
```json
"version": "2.4.0",
```

**Plik:** `pyproject.toml`
```toml
version = "2.4.0"
```

**Plik:** `CHANGELOG.md` — dodaj na górze:
```markdown
## 2.4.0 — Dead code cleanup and production detox

This release removes accumulated dead code (post-refactor orphans, legacy fallbacks)
and strips test-compat hacks that had wormed into production code over multiple
refactors. No user-facing changes; integration behavior is unchanged.

### Removed — Dead code
- 3 orphaned scanner mixin modules (`_scanner_capabilities_mixin.py`, `_scanner_registers_mixin.py`, `_scanner_transport_mixin.py`) left over from the `scanner/` package refactor (v2.3.4–v2.3.9). No remaining imports anywhere (1312 lines total).
- `register_addresses.py` — unused legacy module with hand-defined register address constants that were never imported.
- `validate.yaml` from repository root — stale CI config in wrong location (GitHub Actions only reads `.github/workflows/`).
- `vulture` from `requirements-dev.txt` — not used by any CI job.
- Pyflakes step from `.github/workflows/ci.yaml` — Ruff's `F` rules cover Pyflakes natively.

### Removed — _compat.py cleanup
- 7 fallback blocks for HA symbols that were only triggered when Home Assistant was not installed. File shrunk from 144 to ~40 lines as a clean re-export module.

### Removed — Production detox
- `_update_failed_exception` in coordinator — no longer scans `sys.modules` for test modules to build compatibility `UpdateFailed` subclasses. Direct `UpdateFailed` used everywhere.
- `__init__.py` alias registering `custom_components.thessla_green_modbus.__init__.er` in `sys.modules`. Tests now use standard `monkeypatch.setattr` paths.
- `entity_mappings.py` shim. All imports updated to `from .mappings import X`.
- `_async_patch_coordinator_compat` and `_PermissiveCapabilities` fallback class that returned `True` for every capability access.
- `_SafeDTUtil` defensive wrapper. Direct `homeassistant.util.dt` is re-exported.
- `super().__init__()` TypeError fallback in `ThesslaGreenModbusCoordinator.__init__`.
- `_FallbackFlowBase` in `config_flow.py` — unused class pretending to be ConfigFlow.
- `_VolInvalid` + `vol.Invalid = VOL_INVALID` monkey-patch of voluptuous at import time.
- 7-level fallback in `_required` helper; direct `vol.Required` is used.
- `getattr(self.entry, "async_start_reauth", None)` defensive access in coordinator.

### Changed
- `except BaseException` with `exc.__class__.__name__ == "UpdateFailed"` string comparison replaced with clean `except Exception` + `isinstance(exc, UpdateFailed)`.
- Consolidated `is_request_cancelled_error` into single definition in `scanner/io.py`. Old `scanner_io.py` module is now re-export shim.

### Added
- `tools/compare_registers_with_reference.py` — cross-validates integration register JSON against `airpack4_modbus.json` (vendor reference generated from PDF).
- `tests/test_registers_vs_reference.py` — automated test ensuring integration's register list matches vendor reference; extras must be bitmap-decoded or whitelisted with justification.
- CI step running `compare_registers_with_reference.py` on every PR.

### Migration notes for test writers
- Do not define `class UpdateFailed(Exception)` in tests. Use `from homeassistant.helpers.update_coordinator import UpdateFailed`.
- Do not use `SimpleNamespace` as a coordinator stub. Use `MagicMock(spec=ThesslaGreenModbusCoordinator)` or `pytest-homeassistant-custom-component` fixtures.
- Do not patch `dt_util.utcnow = lambda: "some-string"`. Use `freezegun` or patch to a real datetime.
- Do not patch `voluptuous.Invalid` or `voluptuous.Required`. These are stable APIs.
- Import from `.mappings` not `.entity_mappings` (shim removed).
```

---

## Notatki końcowe

**Dlaczego to jest major bump (2.4.0):**
- Test API się zmienia (niektóre wewnętrzne symbole znikają).
- Testy wymagają przepisania na `pytest-homeassistant-custom-component`.
- Formalnie, integracja z punktu widzenia użytkownika zachowuje się identycznie.
- HACS / HA nie widzą różnicy. Instalacje nie wymagają rekonfiguracji.

**Ryzyko regresu — zróżnicowane:**

- **Grupa A (Fixy #1-#4)** — zero ryzyka. Usuwamy pliki bez importów, martwe CI config.
- **Grupa B (Fix #5)** — niskie ryzyko. `_compat.py` bez martwych fallbacków, wszystkie symbole re-exported.
- **Grupa C (Fix #6)** — czysto dodające. Nowe narzędzie i test.
- **Grupa D (Fix #7)** — niskie ryzyko. Konsolidacja z shimem backward-compat.
- **Grupa E (Fixy #8-#17)** — **średnie ryzyko**. Oczekuj padających testów. Fix poprzez naprawę testów, nie cofanie produkcji.

**Strategia wdrożeniowa:**

Jeśli masz wahania — wdrażaj w podziale:
- **PR 1:** Grupa A+B+C+D (Fixy #1-#7) — minor bump do 2.3.10.
- **PR 2:** Grupa E (Fixy #8-#17) — major bump do 2.4.0, po przepisaniu testów.

Jeśli chcesz jeden release — commit-by-commit po kolejności 1-17, weryfikacja po każdym, ostateczny tag jako 2.4.0.

**Gdy fix staje się niemożliwy:** jeżeli któryś test polega na smell'u i jego przepisanie wymaga znajomości domeny której nie ma, **zostaw komentarz `# TODO(v2.4.0 detox):`** i jedź dalej. Dług kosmetyczny jest lepszy niż martwy kod w produkcji.

**Co ten release daje:**
- Bezpośrednio: ~1400-1700 linii mniej kodu produkcyjnego.
- Pośrednio: kod który testujemy to kod który użytkownik uruchamia. Po odtruciu od test-compat, zieloność testów = jakość kodu. Przed odtruciem, zieloność mogła być osiągana przez *"test go tak ułożył by przechodziło"*.
- Wykorzystanie `airpack4_modbus.json` — artefakt z PDF wreszcie czegoś broni.
- Lżejsze CI, mniej plików do czytania przy onboardingu.
