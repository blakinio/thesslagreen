# Wytyczne dla Codexa — thessla_green_modbus

Repo: `github.com/blakinio/thesslagreen`
Commit bazowy: `766185d`

## Tryb pracy

Pracuj autonomicznie aż do pełnego zakończenia zadania.
Nie zatrzymuj się po częściowym postępie.
Jeśli trafisz na błędy, sam je diagnozuj i kontynuuj.
Po istotnych zmianach uruchamiaj odpowiednie testy lub sprawdzenia.
Wróć dopiero wtedy, gdy:
1. wdrożysz rozwiązanie,
2. zweryfikujesz, że działa,
3. podsumujesz zmiany,
4. wypiszesz tylko takie blokery, które rzeczywiście wymagają mojej decyzji.

Jeśli potrzebna jest zgoda, napisz dokładnie jaka i dlaczego.

---

## Kontekst stanu repozytorium

| Element | Stan |
|---|---|
| entity_mappings.py refaktor | FAKE — cała treść w `mappings/__init__.py` (1854 linii), submoduły to puste re-eksporty (7-19 linii) |
| scanner_core.py refaktor | częściowo — 2662 → 2499 linii, klasa `ThesslaGreenDeviceScanner` wciąż 2268 linii |
| Pyflakes w CI | REGRESJA — CI czerwone (3 błędy) |
| `except Exception` | regresja: było 0, teraz 2 (`config_flow.py:572`, `scanner_device_info.py:20`) |
| Ruff | 0 błędów (ale ruff honoruje `# noqa`, pyflakes nie) |

Błędy pyflakes:
```
scanner_core.py:10:1: 'dataclasses.asdict' imported but unused
mappings/__init__.py:449:17: local variable '_tp' is assigned to but never used
mappings/__init__.py:468:17: local variable '_tp' is assigned to but never used
```

---

## Priorytet 1 — PILNE: pyflakes regression (CI czerwone)

CI step "Pyflakes (custom_components)" w `.github/workflows/ci.yaml` failuje na 3 błędach wprowadzonych w PR #1315. Pyflakes NIE honoruje `# noqa` — trzeba naprawić strukturalnie.

### A) `custom_components/thessla_green_modbus/scanner_core.py:10`

```python
from dataclasses import asdict  # noqa: F401
```

Komentarz obok sugeruje "test patch compatibility" (patrz `scanner_device_info.py` `_compat_asdict`). To jest zapach kodu — testy patchują `scanner_core.asdict`, więc kod produkcyjny musi re-eksportować symbol z `dataclasses`.

Prawidłowe rozwiązanie: w `scanner_core.py` dodaj explicit re-export:

```python
from dataclasses import asdict as _dataclasses_asdict
asdict = _dataclasses_asdict  # re-exported for test monkeypatching
```

Pyflakes zobaczy użycie i nie będzie krzyczeć. Ale LEPSZE rozwiązanie: przestań patchować `dataclasses.asdict` w testach, patchuj konkretną funkcję `scanner_device_info._compat_asdict`.

### B) `custom_components/thessla_green_modbus/mappings/__init__.py:449,468`

Dwukrotnie `_tp = ...` jest przypisane ale nieużyte. Sprawdź kontekst — prawdopodobnie pozostałość po refaktorze. Usuń albo faktycznie użyj.

**Weryfikacja:** `pyflakes custom_components/` zwraca 0. Uruchom lokalnie przed commitem.

---

## Priorytet 2 — regresja `except Exception`

Poprzedni prompt zawęził wszystkie `except Exception` w `custom_components/` do zera. Po ostatnich PR-ach są znowu dwa.

### 1. `custom_components/thessla_green_modbus/scanner_device_info.py:20`

```python
try:
    from . import scanner_core as _scanner_core
    return _scanner_core.asdict(obj)
except Exception:  # pragma: no cover - fallback
    return dataclasses.asdict(obj)
```

Tutaj naprawdę może polecieć: `ImportError` (cykl importu), `AttributeError` (asdict nie wyeksportowany), `TypeError` (niewłaściwy obiekt przekazany do asdict). Zamień na:

```python
except (ImportError, AttributeError, TypeError):
```

### 2. `custom_components/thessla_green_modbus/config_flow.py:572`

```python
except Exception as exc:
```

Przeanalizuj kontekst (co to za operacja) i zamień na konkretne wyjątki. Prawdopodobnie to probing połączenia, więc:

```python
except (ModbusException, ConnectionException, TimeoutError, OSError, ValueError)
```

**NIE** łap `CancelledError`, reraise go.

### Guard na przyszłość

Dodaj do `pyproject.toml` `[tool.ruff.lint]`:

```toml
select = [..., "BLE"]  # BLE001: blind except Exception
```

żeby ruff pilnował tego na przyszłość.

---

## Priorytet 3 — test regresyjny schedule_summer (bug FW 3.11)

Historia projektu: na firmware AirPack4 3.11 batch read FC03 na rejestrach `schedule_summer` addr 15-30 zwraca skorumpowane bajty, co powoduje revert zapisu harmonogramu. Jest fallback `_read_holding_individually` w `_coordinator_io.py`.

Dodaj `tests/test_schedule_summer_regression.py`:

- mockuje transport tak, żeby batch read dla zakresu obejmującego `schedule_summer` rzucał `ModbusIOException` z komunikatem "corrupt" albo zwracał `response.registers = []`
- woła `coordinator._read_holding_registers_optimized()`
- weryfikuje że:
  1. `_read_holding_individually` zostało wywołane (spy/mock)
  2. Każdy rejestr `schedule_summer` został odczytany pojedynczo
  3. `coord.data['schedule_summer_*']` ma oczekiwane wartości z indywidualnych odczytów
  4. `coord._failed_registers` NIE zawiera tych rejestrów (bo fallback się powiódł)

Użyj fixture `coordinator` z `test_coordinator_io.py` jako wzorca. Parametryzuj test dla obu ścieżek: batch raises vs batch returns empty.

Ten test zapobiegnie cichemu usunięciu fallbacku w przyszłym refaktorze.

---

## Priorytet 4 — prawdziwy refaktor `mappings/`

Poprzedni refaktor `entity_mappings.py` był cargo-cult:
- `mappings/__init__.py` ma 1854 linie (cała zawartość)
- `mappings/_helpers.py`, `_loaders.py`, `legacy.py`, `special_modes.py` mają po 7-19 linii i są TYLKO `from . import X; __all__ = ["X"]`

To jest gorsze niż przed refaktorem — mamy te same 1854 linie w jednym pliku PLUS 4 pliki-atrapy które tworzą fałszywą iluzję modularności. Napraw to naprawdę:

### Kroki

1. **`mappings/_helpers.py`** — PRZENIEŚ tutaj faktyczne definicje: `_infer_icon`, `_get_register_info`, `_parse_states`, `_number_translation_keys`, `_load_translation_keys`. Usuń `from . import (_infer_icon, ...)` — to było odwrotnie.

2. **`mappings/_loaders.py`** — PRZENIEŚ tutaj: `_load_number_mappings`, `_load_discrete_mappings`, `_extend_entity_mappings_from_registers`, `_build_entity_mappings`.

3. **`mappings/legacy.py`** — PRZENIEŚ tutaj: `LEGACY_ENTITY_ID_ALIASES` (stała słownikowa) + `map_legacy_entity_id` (funkcja).

4. **`mappings/special_modes.py`** — PRZENIEŚ tutaj: `SPECIAL_MODE_ICONS` + pokrewne stałe.

5. **`mappings/__init__.py`** zostaje jako KONTROLER który:
   - importuje z submodułów
   - buduje globalne słowniki (`ENTITY_MAPPINGS` etc.)
   - re-eksportuje publiczne API przez `__all__`
   - uruchamia `_build_entity_mappings()` na końcu
   - CEL: < 300 linii

6. Żaden submoduł nie ma > 600 linii.

7. **`custom_components/thessla_green_modbus/entity_mappings.py`** — zachowaj obecny shim (to OK), ale rozważ usunięcie hacku `sys.modules[__name__] = _m` bo to mask dla problemów z import order. Alternatywnie:

   ```python
   from .mappings import *  # noqa: F401,F403
   from .mappings.legacy import map_legacy_entity_id  # noqa: F401
   ```

### Weryfikacja

- pytest przechodzi bez zmian w testach
- `ruff check .` + pyflakes + mypy = 0 błędów
- `validate_entity_mappings.py` + `check_translations.py` nadal OK
- `wc -l custom_components/thessla_green_modbus/mappings/*.py` pokazuje że żaden plik nie dominuje (nie ma `__init__.py` z 1800+ linii)

---

## Priorytet 5 — refaktor klasy `ThesslaGreenDeviceScanner` (2268 linii)

`scanner_core.py` skurczył się z 2662 do 2499 linii, ale sama klasa `ThesslaGreenDeviceScanner` od linii 232 do 2499 ma **2268 linii**. Pomocnicze funkcje wyciągnięto (`scanner_io`, `scanner_device_info`, `scanner_register_maps`), ale klasa pozostała god-objectem.

Zastosuj wzorzec mixinów jak przy `ThesslaGreenModbusCoordinator`:

### Pogrupuj metody klasy

**A) `_scanner_transport_mixin.py`** — setup połączenia, `_establish_connection`, `_try_tcp`, `_try_rtu`, `_try_tcp_rtu`, `close()`, `disconnect()`, `is_connected()`, `_detect_connection_mode`

**B) `_scanner_registers_mixin.py`** — `_scan_holding_registers`, `_scan_input_registers`, `_scan_coil_registers`, `_scan_discrete_inputs`, `_build_available_registers`, `_probe_register`, `_probe_register_range`

**C) `_scanner_capabilities_mixin.py`** — `detect_capabilities`, `_apply_capability_rules`, `_derive_device_info`, `_detect_firmware`, `_detect_model`

**D) `_scanner_diagnostic_mixin.py`** — format diagnostyczny wyników, `_format_scan_result`, `_summarize_scan`

**E) `scanner_core.py`** — tylko klasa `ThesslaGreenDeviceScanner` dziedzicząca po mixinach + `__init__` + `scan_device()` (orchestrator)

### Wymagania

- zero zmian publicznego API (testy nie ruszamy)
- każdy mixin ma `Protocol` z atrybutami których używa z `self` (`transport`, `client`, `_registers`, `_host`, `_port` itd.) — używaj `TYPE_CHECKING`
- pytest + ruff + pyflakes + mypy → 0 błędów
- **CEL:** `scanner_core.py` < 800 linii, każdy mixin < 600 linii

Rób per-mixin w osobnym commicie żeby łatwo zrewertować jeśli coś się wysypie.

---

## Kolejność wykonania

1. **Priorytet 1** (pyflakes, 5 min — CI jest zepsute, nawet jeśli PR przechodzi)
2. **Priorytet 2** (2 regresje `except Exception`, 10 min)
3. **Priorytet 3** (test regresyjny dla buga FW 3.11)
4. **Priorytet 4** (prawdziwy refaktor mappings — to jest dług w obecnej formie)
5. **Priorytet 5** (refaktor klasy scannera — największe, ale idzie czystym wzorcem)

Po 1+2 repo wraca do czystego stanu. 3+4+5 to porządne domknięcie refaktorów, które zostały zrobione tylko pozornie.

---

## Komendy weryfikacyjne (uruchamiaj po każdej istotnej zmianie)

```bash
ruff check custom_components/
ruff check .
pyflakes custom_components/
python -m pytest -q
python tools/validate_entity_mappings.py
python tools/check_translations.py
python tools/validate_registers.py
PYTHONPATH=. python tools/validate_dashboard_entities.py example_dashboard.yaml
```

Wszystkie muszą zwracać 0 błędów / "OK" / "All checks passed" przed zakończeniem zadania.
