# Codex Fix Guide — ThesslaGreen Modbus Integration

Analiza kodu wykonana 2026-04-12. Poniżej lista problemów do naprawy,
pogrupowana wg priorytetu (KRYTYCZNE > WAŻNE > KOSMETYCZNE).

---

## KRYTYCZNE — bugi i błędy konfiguracji

### 1. `.bandit` to nie konfiguracja bandit — to workflow YAML

**Plik:** `.bandit`

Plik `.bandit` zawiera kompletny workflow GitHub Actions (198 linii YAML, `name: CI`),
a **nie** konfigurację narzędzia bandit. Job `security` w CI (`ci.yaml` lub `.bandit`
linijka ~168) odwołuje się do `config_file: .bandit`, co powoduje że bandit parsuje
YAML workflow zamiast listy wykluczeń.

**Fix:**
- Usunąć `.bandit` (jest duplikatem `.github/workflows/ci.yaml`) **lub** zastąpić
  zawartość prawdziwą konfiguracją bandit, np.:
  ```ini
  [bandit]
  exclude = tests,tools
  ```

---

### 2. Niezgodność wersji: `manifest.json` vs `pyproject.toml`

| Plik | Wersja |
|------|--------|
| `manifest.json` | **2.3.0** |
| `pyproject.toml` | **2.2.0** |

**Fix:** Zsynchronizować wersje — ustawić tę samą wartość w obu plikach.

---

### 3. Niezgodność wymaganej wersji Pythona: README vs pyproject.toml

| Plik | Wymóg |
|------|-------|
| `README.md` linia 6 | Python **3.12+** |
| `pyproject.toml` linia 24 | `requires-python = ">=3.13"` |
| `pyproject.toml` classifiers | `Programming Language :: Python :: 3.13` |
| ruff / black / mypy target | `py313` |

**Fix:** README powinien mówić **Python 3.13+**, albo `pyproject.toml` powinien
obniżyć wymaganie do `>=3.12` (i ustawić `target-version = "py312"` w ruff/black/mypy).

---

### 4. Duplikaty kluczy w słowniku tłumaczeń (F601 — bug)

**Plik:** `tools/translate_register_descriptions.py`

Ruff znalazł 2 powtórzone klucze literalne:
- Linia **219**: `"Zbyt wysoka temperatura przed rekuperatorem"` — zduplikowany klucz,
  drugie wystąpienie nadpisze pierwsze (cichy bug).
- Linia **233**: `"Nie zadziałało zabezpieczenie przeciwzamrożeniowe wymiennika rekuperacyjnego (FPX)"` — j.w.

**Fix:** Znaleźć oba duplikaty, porównać wartości (tłumaczenia EN) i usunąć
nadmiarowe wpisy lub poprawić klucze jeśli to inne warianty.

---

### 5. Niebezpieczne porównywanie wyjątków przez nazwę klasy

**Plik:** `custom_components/thessla_green_modbus/__init__.py` linie 314, 319, 346, 351

```python
if exc.__class__.__name__ == "ConfigEntryNotReady":
    raise
```

Porównanie `__name__` zamiast `isinstance()` jest kruche — jeśli wyjątek jest
opakowany (proxy, podklasa), warunek nie zadziała.

**Fix:** Zamienić na `isinstance(exc, ConfigEntryNotReady)` — klasa jest
importowana w tej samej funkcji (linia 298).

---

### 6. Potencjalny KeyError w cache rejestrów

**Plik:** `custom_components/thessla_green_modbus/registers/loader.py` linie 560, 576

```python
mtime = _cached_file_info[str(path)][0]
```

Jeśli `registers_sha256()` nie wypełni `_cached_file_info` (np. plik niedostępny),
ten kod rzuci `KeyError` bez czytelnego komunikatu.

**Fix:** Użyć `_cached_file_info.get(str(path))` z obsługą `None` i jasnym
komunikatem błędu.

---

## WAŻNE — architektura, performance, poprawność

### 7. Potencjalny deadlock — niejasna hierarchia locków

**Plik:** `custom_components/thessla_green_modbus/coordinator.py` linie 385-386

Dwa asyncio.Lock: `_client_lock` i `_write_lock`. Brak udokumentowanej kolejności
ich nabywania. Jeśli operacja zapisu (trzymając `_write_lock`) wywoła reconnect
(potrzebujący `_client_lock`), a inna ścieżka robi to odwrotnie, powstaje deadlock.

**Fix:** Udokumentować i wymusić kolejność: zawsze `_client_lock` przed `_write_lock`,
albo scalić w jeden lock.

---

### 8. Globalne mutowalne zmienne w `const.py` (race condition)

**Plik:** `custom_components/thessla_green_modbus/const.py` linie 441-478

`async_setup_options()` modyfikuje globalne zmienne modułowe (`SPECIAL_MODE_OPTIONS`,
`DAYS_OF_WEEK`, `MODBUS_PARITY` itp.) za pomocą `global`. Przy równoczesnym
ładowaniu wielu config entries, `asyncio.gather()` może powodować interleaving.

**Fix:** Użyć `asyncio.Lock` wokół inicjalizacji globalnych opcji, lub przenieść
opcje do instancji koordynatora.

---

### 9. Brak cleanup listenera przy nieudanym setup

**Plik:** `custom_components/thessla_green_modbus/__init__.py` linia ~459

`entry.add_update_listener()` jest rejestrowany wcześnie w `async_setup_entry`, ale
jeśli setup nie powiedzie się po tym punkcie, listener nie jest usuwany.

**Fix:** Dodać cleanup w bloku `except` lub użyć wzorca `try/finally`.

---

### 10. Zduplikowany kod `_percentage_limits()` i `_write_register()`

**Pliki:**
- `climate.py:225` i `fan.py:122` — identyczna metoda `_percentage_limits()`
- `climate.py:291`, `fan.py:275`, `switch.py:187` — 3x `_write_register()`

**Fix:** Przenieść do klasy bazowej `ThesslaGreenEntity` w `entity.py`.

---

### 11. Hardcoded magic numbers

| Wartość | Lokalizacja | Opis |
|---------|-------------|------|
| `15.0`, `35.0` | `climate.py:120-121` | min/max temperatura |
| `150` | `climate.py:237`, `fan.py:134` | max procent wentylacji |
| `0.5` | `climate.py:119,122` | krok/precyzja temperatury |
| `10` | `fan.py:85` | `speed_count` |
| `50` | `fan.py:178` | domyślny procent po turn_on |
| `4096` | `diagnostics.py:53` | próg wersji config flow |
| `(4452, 4460)` | `scanner_helpers.py:87` | UART optional registers |

**Fix:** Przenieść do `const.py` jako nazwane stałe.

---

### 12. Niespójne logiki `available` między platformami

| Platforma | Logika available |
|-----------|-----------------|
| `entity.py` (bazowa) | `last_update_success AND data[key] is not None AND not offline` |
| `number.py:252` | Zawsze `True` gdy coordinator dostępny (brak sprawdzenia danych) |
| `fan.py:90` | Wymaga `on_off_panel_mode` w data |
| `select.py:96` | BCD registers dostępne nawet bez danych |

**Fix:** Ujednolicić — bazowa klasa powinna obsłużyć wszystkie przypadki,
a platformy nadpisują tylko gdy mają specjalny powód.

---

### 13. Ciche połykanie błędów w `select.py`

**Plik:** `custom_components/thessla_green_modbus/select.py` linie 129-147

`async_select_option()` łapie błędy i zwraca `None` zamiast rzucać wyjątek.
Inne encje (fan, switch) rzucają wyjątki, co jest spójniejsze z HA API.

**Fix:** Rzucać `HomeAssistantError` po zalogowaniu błędu, jak robią to inne
platformy.

---

### 14. Słabe WeakKeyDictionary cache w hot path

**Plik:** `custom_components/thessla_green_modbus/modbus_helpers.py` linie 19-24

`_KWARG_CACHE` i `_SIG_CACHE` używają `WeakKeyDictionary`. Jeśli referencje do
funkcji zostaną zebrane przez GC, każdy uncached call do `_call_modbus` wykonuje
kosztowną inspekcję `inspect.signature()`.

**Fix:** Rozważyć zwykły `dict` z bounded size (LRU) lub `functools.lru_cache`.

---

### 15. Synchroniczne I/O w ścieżce async

**Plik:** `custom_components/thessla_green_modbus/const.py` linia ~427

`_load_json_option()` używa synchronicznego `read_text()` nawet gdy
`async_setup_options()` jest async. Offloading na executor działa tylko gdy `hass`
jest podane.

**Fix:** Zawsze używać `await hass.async_add_executor_job()` lub `asyncio.to_thread()`.

---

### 16. Runtime type() fallbacks w climate.py łamią type-checkery

**Plik:** `custom_components/thessla_green_modbus/climate.py` linie 14-24

```python
HVACAction = getattr(climate_component, "HVACAction",
    type("HVACAction", (), {"OFF": "off", ...}))
```

Dynamiczne tworzenie klas przez `type()` łamie mypy/Pylance i generuje E402/I001
(42 naruszenia w ruff).

**Fix:** Przenieść do osobnego `_compat.py` lub użyć bloku `TYPE_CHECKING` z
odpowiednimi importami warunkowymi.

---

## KOSMETYCZNE — lint, styl, cleanup

### 17. Ruff: 292 naruszenia (auto-fix: 32)

Rozkład:
| Reguła | Ilość | Opis |
|--------|-------|------|
| E501 | 206 | Linia >100 znaków |
| E402 | 42 | Import nie na górze pliku |
| B010 | 16 | `setattr()` ze stałą |
| UP017 | 9 | Użyj `datetime.UTC` zamiast `timezone.utc` |
| I001 | 7 | Niesortowane importy |
| UP037 | 3 | Zbędne cudzysłowy w annotacjach |
| F401 | 2 | Unused imports: `datetime` w `services.py:7`, `re` w `tools/translate_register_descriptions.py:14` |

**Fix:** Uruchomić `ruff check --fix` (32 auto-fixy), potem ręcznie naprawić E501
i E402.

---

### 18. Szerokie `# type: ignore` bez kodów

**Pliki:** `__init__.py:80-82`, `config_flow.py:23,28,34`, `coordinator.py:92,94,95`

**Fix:** Dodać kody naruszeń: `# type: ignore[assignment]`, `# type: ignore[attr-defined]`.

---

### 19. `sys.modules` manipulation shim

**Plik:** `custom_components/thessla_green_modbus/__init__.py` linie 90-92

```python
_init_alias = sys.modules.setdefault(f"{__name__}.__init__", sys.modules[__name__])
setattr(_init_alias, "er", er)
```

Niestandardowa manipulacja `sys.modules` dla kompatybilności z testami. Generuje
B010 w ruff.

**Fix:** Przenieść do conftest.py w testach, usunąć z kodu produkcyjnego.

---

### 20. Unused import + StrEnum fallback

- `services.py:7` — `datetime` imported but unused (F401)
- `registers/schema.py:29` — `class StrEnum(str, Enum)` zamiast `enum.StrEnum` (UP042)
- `config_flow.py:549` — `asyncio.TimeoutError` redundant z `TimeoutError` (UP041)

**Fix:** Usunąć unused imports, użyć `enum.StrEnum` (Python 3.11+).

---

## Podsumowanie priorytetów

| Priorytet | Pozycje | Wysiłek |
|-----------|---------|---------|
| **KRYTYCZNE** | #1-6 | Małe fixy, duży wpływ |
| **WAŻNE** | #7-16 | Średni refactoring |
| **KOSMETYCZNE** | #17-20 | `ruff --fix` + ręczne poprawki |

### Sugerowana kolejność pracy Codex:

1. Fix #1 (`.bandit`) — 1 min
2. Fix #2-3 (wersje) — 2 min
3. Fix #4 (duplikaty kluczy) — 5 min
4. Fix #5 (isinstance) — 5 min
5. Fix #6 (KeyError guard) — 5 min
6. Fix #17 (`ruff --fix`) — 1 min auto
7. Fix #10 (deduplikacja metod) — 15 min
8. Fix #11 (magic numbers → const.py) — 10 min
9. Fix #12-13 (availability + error handling) — 15 min
10. Reszta — wg priorytetów
