# thessla_green_modbus — instrukcja napraw dla Claude Code (v4)

**Repozytorium:** `github.com/blakinio/thesslagreen`
**Branch:** `main` (HEAD: `751cb7e` — merge PR #1326)
**Wersja docelowa:** `2.3.2 → 2.3.3`
**Data audytu:** 2026-04-16

---

## Stan wyjściowy po v2.3.2

**Co już działa (nie ruszać):**
- ✅ **Ruff:** 1 finding (`UP042` w `registers/schema.py:29`) — adresowane w Fix #1 tego audytu.
- ✅ **Mypy strict:** 0 błędów w 49 plikach, **bez żadnych wykluczeń** w `pyproject.toml`. Spadek z 343 (v2.3.1) → 0. Fixy v3 zadziałały w 100%.
- ✅ Modern HA API: `entry.runtime_data` + `async_forward_entry_setups` (brak deprecated `hass.data[DOMAIN]`).
- ✅ Brak `TODO`/`FIXME`/`HACK`/`XXX` w custom_components.
- ✅ Brak blokujących wywołań (`time.sleep`, `requests.*`) w kodzie asynchronicznym.

**Co tym audytem bierzemy na tapetę — czystki po skończonej migracji typów:**

Po v2.3.2 CI jest zielony, ale są problemy, które nie były w zakresie v3 (bo v3 celował wyłącznie w mypy):

1. **Martwy kod kompatybilnościowy** — `StrEnum` fallback dla py<3.11, podczas gdy manifest/pyproject wymagają py>=3.13.
2. **Duplikacja kodu w critical path** — `_async_update_data` w coordinator ma 3 prawie identyczne bloki `except` (~45 linii DRY).
3. **Obsługa `asyncio.CancelledError`** — `_async_update_data` łapie `OSError, ValueError` po wszystkich innych, ale nie wyłącza jawnie `CancelledError`. W nowszym asyncio `CancelledError` dziedziczy z `BaseException`, nie z `Exception`, więc *obecnie* nie jest łapane — ale warto to uczynić jawnym dla bezpieczeństwa przy refactorze + zapewnić czyste zamknięcie transportu.
4. **24-parametrowy konstruktor** w `ThesslaGreenModbusCoordinator` — kandydat do dataclass config.
5. **Zbędna property indirekcja** — `client` property ↔ `_client` attribute bez logiki walidującej/logującej.

**Rozkład na pliki:**

```
 1548  coordinator.py                  ← Fix #2, #3, #4, #5 (największy ROI)
  516  registers/schema.py             ← Fix #1 (najprostszy)
 2512  scanner_core.py                 ← Fix #6 (największy refactor; zostaje na osobny PR)
 1108  services.py                     ← Fix #7 (mniejszy, kosmetyka)
```

**Zalecana kolejność wdrożenia:**
1. **Fix #1** — `StrEnum` fallback cleanup (1 plik, 10 linii).
2. **Fix #2** — ekstrakcja `_handle_update_error` z `_async_update_data` (1 plik, ~45 linii zmian).
3. **Fix #3** — wyłączenie `CancelledError` z ogólnego `except` (1 plik, 3 linijki).
4. **Fix #4** — `@staticmethod _parse_backoff_jitter` (1 plik, ~20 linii zmian).
5. **Fix #5** — uproszczenie `client` property lub udokumentowanie powodu indirekcji.
6. **Fix #6** — **osobny PR, nie w tym release** — split `scanner_core.py`.
7. **Fix #7** — **osobny PR, nie w tym release** — konsolidacja duplikacji w `services.py`.

Po każdym Fixie:
```bash
mypy custom_components/thessla_green_modbus/
ruff check custom_components/thessla_green_modbus/ tests/ tools/
pytest -x -q
```

---

## Fix #1 — Usuń martwy `StrEnum` fallback dla Python <3.11

**Plik:** `custom_components/thessla_green_modbus/registers/schema.py`

**Dowód problemu:**
```
UP042 Class StrEnum inherits from both `str` and `enum.Enum`
  --> custom_components/thessla_green_modbus/registers/schema.py:29:11
   |
29 |     class StrEnum(str, Enum):  # type: ignore[no-redef]
   |           ^^^^^^^
   |
help: Inherit from `enum.StrEnum`
```

`pyproject.toml`:
```toml
requires-python = ">=3.13"

[tool.ruff]
target-version = "py313"
```

Manifest integracji wymaga `homeassistant: 2026.1.0`, który sam wymaga Python ≥3.13. Fallback `try: from enum import StrEnum; except ImportError: ... class StrEnum(str, Enum): ...` jest martwy — `enum.StrEnum` jest w stdlib od Python 3.11. Ruff sugeruje `enum.StrEnum` jako base — ale skoro cała gałąź fallbackowa to martwy kod, prostsze jest po prostu usunięcie try/except.

### Krok 1 — zastąp try/except bezpośrednim importem

#### SZUKAJ (linie ~19-31)
```python
from __future__ import annotations

import logging
import re

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Compatibility StrEnum fallback for Python < 3.11."""

from typing import Any, Literal, cast
```

#### ZASTĄP
```python
from __future__ import annotations

import logging
import re
from enum import StrEnum
from typing import Any, Literal, cast
```

**Weryfikacja:** sprawdź, czy `Enum` jest jeszcze używany gdziekolwiek w pliku:
```bash
grep -n "\bEnum\b" custom_components/thessla_green_modbus/registers/schema.py
```
Jeśli nie pojawia się nigdzie poza wyrzuconym fallbackiem, import `Enum` nie jest potrzebny (w powyższym bloku `ZASTĄP` już go nie ma).

### Oczekiwany efekt
- `ruff check` → 0 findings.
- `mypy` bez zmian (był czysty).
- Import `StrEnum` z stdlib — brak subtelnych różnic vs fallback `class StrEnum(str, Enum)` (stdlib jest *źródłem* tej klasy).

---

## Fix #2 — Ekstrakcja `_handle_update_error` z `_async_update_data`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód problemu (linie 1199-1241):**
```python
            except (ModbusException, ConnectionException) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("connection_failure")

                if is_invalid_auth_error(exc):
                    self._trigger_reauth("invalid_auth")

                _LOGGER.error("Failed to update data: %s", exc)
                raise _update_failed_exception(f"Error communicating with device: {exc}") from exc
            except TimeoutError as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["timeout_errors"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("timeout")

                _LOGGER.warning("Data update timed out: %s", exc)
                raise _update_failed_exception(f"Timeout during data update: {exc}") from exc
            except (OSError, ValueError) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("connection_failure")

                _LOGGER.error("Unexpected error during data update: %s", exc)
                raise UpdateFailed(f"Unexpected error: {exc}") from exc
```

**43 linie z `failed_reads += 1`, `consecutive_failures += 1`, `offline_state = True`, `_disconnect()`, `_consecutive_failures >= _max_failures` — powtórzone 3×.** Różnice:
- Typ wyjątku.
- `TimeoutError` dodatkowo inkrementuje `timeout_errors`.
- `_trigger_reauth` reason: `"connection_failure"` / `"timeout"` / `"connection_failure"` (dwa identyczne).
- `ModbusException|ConnectionException` dodatkowo sprawdza `is_invalid_auth_error(exc)` i wywołuje drugi `_trigger_reauth("invalid_auth")`.
- Log level: `error` / `warning` / `error`.
- Komunikat wyjątku: `"Error communicating with device"` / `"Timeout during data update"` / `"Unexpected error"`.
- Typ wyjścia: `_update_failed_exception` / `_update_failed_exception` / `UpdateFailed` (*subtelna niespójność!* — trzeci używa surowego `UpdateFailed`, reszta helpera).

**Uwaga:** niespójność `_update_failed_exception` vs `UpdateFailed` (linia 1241) może być zamierzona, ale nie ma komentarza wyjaśniającego. Należy to rozstrzygnąć przy refactorze — albo ujednolicić, albo udokumentować.

### Krok 2a — dodaj helper `_handle_update_error`

Dodaj nową metodę w klasie `ThesslaGreenModbusCoordinator`, **przed** `_async_update_data` (czyli przed linią 1141):

```python
    async def _handle_update_error(
        self,
        exc: Exception,
        *,
        reauth_reason: str,
        message: str,
        log_level: int = logging.ERROR,
        timeout_error: bool = False,
        check_auth: bool = False,
        use_helper: bool = True,
    ) -> UpdateFailed:
        """Common error-handling path for ``_async_update_data``.

        Updates statistics, increments failure counters, disconnects transport,
        triggers reauth when thresholds are reached, logs, and returns the
        ``UpdateFailed`` exception instance the caller should raise.

        Returning (rather than raising) keeps the control flow explicit in
        ``_async_update_data`` — each except branch still has its own
        ``raise ... from exc`` line.
        """
        self.statistics["failed_reads"] += 1
        if timeout_error:
            self.statistics["timeout_errors"] += 1
        self.statistics["last_error"] = str(exc)
        self._consecutive_failures += 1
        self.offline_state = True
        await self._disconnect()

        if self._consecutive_failures >= self._max_failures:
            _LOGGER.error("Too many consecutive failures, disconnecting")
            self._trigger_reauth(reauth_reason)

        if check_auth and is_invalid_auth_error(exc):
            self._trigger_reauth("invalid_auth")

        _LOGGER.log(log_level, "%s: %s", message, exc)
        full_message = f"{message}: {exc}"
        if use_helper:
            return _update_failed_exception(full_message)
        return UpdateFailed(full_message)
```

**Import `logging` na górze pliku** — sprawdź, czy jest (powinien być, coordinator używa `_LOGGER`):
```bash
grep -n "^import logging" custom_components/thessla_green_modbus/coordinator.py
```

### Krok 2b — zastąp 3 bloki `except` wywołaniami helpera

#### SZUKAJ (linie 1199-1241, trzy bloki except)
```python
            except (ModbusException, ConnectionException) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("connection_failure")

                if is_invalid_auth_error(exc):
                    self._trigger_reauth("invalid_auth")

                _LOGGER.error("Failed to update data: %s", exc)
                raise _update_failed_exception(f"Error communicating with device: {exc}") from exc
            except TimeoutError as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["timeout_errors"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("timeout")

                _LOGGER.warning("Data update timed out: %s", exc)
                raise _update_failed_exception(f"Timeout during data update: {exc}") from exc
            except (OSError, ValueError) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("connection_failure")

                _LOGGER.error("Unexpected error during data update: %s", exc)
                raise UpdateFailed(f"Unexpected error: {exc}") from exc
```

#### ZASTĄP
```python
            except (ModbusException, ConnectionException) as exc:
                raise await self._handle_update_error(
                    exc,
                    reauth_reason="connection_failure",
                    message="Error communicating with device",
                    check_auth=True,
                ) from exc
            except TimeoutError as exc:
                raise await self._handle_update_error(
                    exc,
                    reauth_reason="timeout",
                    message="Timeout during data update",
                    log_level=logging.WARNING,
                    timeout_error=True,
                ) from exc
            except (OSError, ValueError) as exc:
                raise await self._handle_update_error(
                    exc,
                    reauth_reason="connection_failure",
                    message="Unexpected error",
                    use_helper=False,
                ) from exc
```

**Uwaga semantyczna:** oryginalny kod logował **trzy różne** komunikaty:
- `"Failed to update data: %s"` (ModbusException/ConnectionException)
- `"Data update timed out: %s"` (TimeoutError)
- `"Unexpected error during data update: %s"` (OSError/ValueError)

…a `UpdateFailed` niósł **inne** komunikaty:
- `"Error communicating with device: {exc}"`
- `"Timeout during data update: {exc}"`
- `"Unexpected error: {exc}"`

Po refactorze używamy **jednego** `message` dla obu (log + wyjątek), bo to i tak koreluje w czasie. Rekomendacja: ujednolicić komunikaty (stan po ZASTĄP wyżej).

### Krok 2c — rozstrzygnij niespójność `_update_failed_exception` vs `UpdateFailed`

Znajdź definicję `_update_failed_exception`:
```bash
grep -n "_update_failed_exception\b" custom_components/thessla_green_modbus/coordinator.py | head -5
grep -rn "def _update_failed_exception\|_update_failed_exception =" custom_components/thessla_green_modbus/
```

Sprawdź, czy helper dodaje coś, czego `UpdateFailed` nie ma (np. prefix z nazwą integracji, specjalne kwargs). Jeśli nie — wywal helper, używaj `UpdateFailed` wszędzie (`use_helper` parametr staje się zbędny). Jeśli tak — udokumentuj w docstringu helpera i **ujednolić na niego wszędzie** (trzeci blok `except` tego nie używa — to wygląda na zapomniane przy refaktorze).

**Decyzja domyślna (zachowawcza):** zostaw `use_helper=True` default, `use_helper=False` dla bloku `OSError|ValueError` — zachowuje obecne zachowanie. Ale dopisz TODO: "Ujednolicić wyjątki — sprawdzić czy `_update_failed_exception` niesie różnicę względem `UpdateFailed`".

### Oczekiwany efekt
- `_async_update_data` kurczy się z ~105 linii → ~75 linii.
- DRY: 43 linie duplikacji → 13 linii wywołań helpera + 30 linii w `_handle_update_error` (jednorazowa lokalizacja logiki).
- Przy dodawaniu nowej ścieżki błędu (np. `SerialException`) wystarczy jeden `except` + wywołanie helpera, zamiast kopiowania 15-liniowego bloku.
- Testy — **wszystkie istniejące testy `test_coordinator.py` muszą nadal przechodzić**. Uruchom:
  ```bash
  pytest tests/test_coordinator.py tests/test_coordinator_coverage.py -x -q
  ```

---

## Fix #3 — Dodaj jawny handler `asyncio.CancelledError`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód problemu:**
W Pythonie 3.8+ `asyncio.CancelledError` dziedziczy z `BaseException` (nie z `Exception`), więc *formalnie* nie jest łapany przez `except (OSError, ValueError)`. **Ale:**

- Obecny kod **nie wywołuje `_disconnect`** przy cancelation — jeśli task zostanie anulowany w trakcie `_read_input_registers_optimized`, transport może zostać w niedokończonym stanie (half-read). Przy kolejnym `_ensure_connection()` może to powodować desynchronizację PDU.
- Jeżeli ktoś w przyszłości rozszerzy listę łapanych wyjątków o `Exception` (np. dla bezpieczeństwa "złap wszystko") — cancellation całego taska zostanie połknięte, co jest trudnym do zdiagnozowania bugiem.

**Rozwiązanie:** dodaj jawny `except asyncio.CancelledError` który `await self._disconnect()` i re-raise.

### Krok 3 — dodaj jawny handler cancellation

Wewnątrz `_async_update_data` (po refactorze z Fix #2), **przed** `except (ModbusException, ConnectionException)` wstaw:

```python
            except asyncio.CancelledError:
                # Don't count cancellation as a failure, but close the transport
                # to avoid leaving it in an inconsistent state mid-read.
                with contextlib.suppress(Exception):
                    await self._disconnect()
                raise
```

**Wymagany import** na górze pliku:
```bash
grep -n "^import contextlib" custom_components/thessla_green_modbus/coordinator.py
```

Jeśli brak — dodaj wśród standardowych importów:
```python
import asyncio
import contextlib  # ← dodać
import logging
```

**Uwaga `asyncio` powinien już być** — coordinator używa `asyncio.Lock()`. Sprawdź:
```bash
grep -n "^import asyncio" custom_components/thessla_green_modbus/coordinator.py
```

### Krok 3b — test regresji

**Plik:** `tests/test_coordinator.py` (dodaj, nie zastępuj)

```python
import asyncio

import pytest


async def test_async_update_data_handles_cancellation(coordinator_with_mock_transport) -> None:
    """Cancellation must close transport but not increment failure counters."""
    coordinator, mock_transport = coordinator_with_mock_transport
    mock_transport.read_input_registers.side_effect = asyncio.CancelledError()

    failed_before = coordinator.statistics["failed_reads"]

    with pytest.raises(asyncio.CancelledError):
        await coordinator._async_update_data()

    assert coordinator.statistics["failed_reads"] == failed_before, (
        "cancellation must not count as failed read"
    )
    # Adjust fixture/mocks to reflect the project's _disconnect plumbing:
    mock_transport.close.assert_called()
```

**Uwaga:** fixture `coordinator_with_mock_transport` może już istnieć pod inną nazwą w `conftest.py` — dostosuj. Szkielet pokazuje intent.

### Oczekiwany efekt
- Cancellation taska (np. podczas unload integracji) zamyka transport zanim propaguje się wyżej.
- Brak statystycznych false-positives ("failed reads").

---

## Fix #4 — Wydziel `_parse_backoff_jitter` jako `@staticmethod`

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód problemu (linie 158-183 — sygnatura, 227-245 — parsowanie):**

**23 parametry** w `__init__` (pomijając `hass` i `self`). Ciało konstruktora ma 180 linii z czego ~50 to walidacja/parsowanie każdego parametru. Najgorszy fragment — `backoff_jitter` — zajmuje 20 linii i jest kandydatem do ekstrakcji.

**Dlaczego tylko jitter, nie cały dataclass:** pełny `CoordinatorConfig` dataclass to breaking change publicznego API. Odłóż na v2.4.0 (osobny PR). Ten fix robi tylko **bezpieczną ekstrakcję** jednej metody, która:
- Jest trudna do przetestowania obecnie (wymaga skonstruować cały coordinator).
- Ma zawiłą logikę (4 gałęzie typu + normalizacja zera).
- Powtarza typecheck-wzorzec `isinstance(x, int | float)` który mypy już wspiera.

### Krok 4a — wydziel `_parse_backoff_jitter`

#### SZUKAJ (linie ~227-245)
```python
        jitter_value: float | tuple[float, float] | None
        if isinstance(backoff_jitter, int | float):
            jitter_value = float(backoff_jitter)
        elif isinstance(backoff_jitter, str):
            try:
                jitter_value = float(backoff_jitter)
            except ValueError:
                jitter_value = None
        elif isinstance(backoff_jitter, list | tuple) and len(backoff_jitter) >= 2:
            try:
                jitter_value = (float(backoff_jitter[0]), float(backoff_jitter[1]))
            except (TypeError, ValueError):
                jitter_value = None
        else:
            jitter_value = None if backoff_jitter in (None, "") else DEFAULT_BACKOFF_JITTER

        if jitter_value in (0, 0.0):
            jitter_value = 0.0
        self.backoff_jitter = jitter_value
```

#### ZASTĄP
```python
        self.backoff_jitter = self._parse_backoff_jitter(backoff_jitter)
```

Następnie dodaj nową `@staticmethod` tuż po `__init__`, przed `@property client`:

```python
    @staticmethod
    def _parse_backoff_jitter(
        value: float | int | str | tuple[float, float] | list[float] | None,
    ) -> float | tuple[float, float] | None:
        """Normalize backoff_jitter input to ``None``, ``float``, or ``(float, float)``.

        Accepts:
            - numeric (int, float) → float
            - string → float via parse, or None if parse fails
            - 2+ element sequence → (float, float) of first two elements
            - None or empty string → None
            - anything else → DEFAULT_BACKOFF_JITTER

        Zero values are normalized to ``0.0`` for downstream consistency.
        """
        result: float | tuple[float, float] | None
        if isinstance(value, int | float):
            result = float(value)
        elif isinstance(value, str):
            try:
                result = float(value)
            except ValueError:
                result = None
        elif isinstance(value, list | tuple) and len(value) >= 2:
            try:
                result = (float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                result = None
        else:
            result = None if value in (None, "") else DEFAULT_BACKOFF_JITTER

        if result in (0, 0.0):
            result = 0.0
        return result
```

### Krok 4b — test bezpośredni dla `_parse_backoff_jitter`

**Plik:** `tests/test_coordinator.py` (dodaj, nie zastępuj)

```python
class TestParseBackoffJitter:
    """Direct tests for the _parse_backoff_jitter parser — no coordinator needed."""

    def test_numeric_inputs(self) -> None:
        from custom_components.thessla_green_modbus.coordinator import (
            ThesslaGreenModbusCoordinator,
        )
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(0) == 0.0
        assert parse(0.0) == 0.0
        assert parse(1) == 1.0
        assert parse(1.5) == 1.5

    def test_string_inputs(self) -> None:
        from custom_components.thessla_green_modbus.coordinator import (
            ThesslaGreenModbusCoordinator,
        )
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse("1.5") == 1.5
        assert parse("0") == 0.0
        assert parse("not-a-number") is None
        assert parse("") is None

    def test_tuple_list_inputs(self) -> None:
        from custom_components.thessla_green_modbus.coordinator import (
            ThesslaGreenModbusCoordinator,
        )
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse((1.0, 2.0)) == (1.0, 2.0)
        assert parse([1, 2]) == (1.0, 2.0)
        assert parse((1.0, 2.0, 3.0)) == (1.0, 2.0)  # extras ignored

    def test_invalid_sequence_returns_none(self) -> None:
        from custom_components.thessla_green_modbus.coordinator import (
            ThesslaGreenModbusCoordinator,
        )
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(["a", "b"]) is None
        assert parse((None, None)) is None

    def test_none_and_sentinel_defaults(self) -> None:
        from custom_components.thessla_green_modbus.coordinator import (
            ThesslaGreenModbusCoordinator,
            DEFAULT_BACKOFF_JITTER,
        )
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(None) is None
        # dict / object falls through to DEFAULT_BACKOFF_JITTER
        assert parse({"key": "value"}) == DEFAULT_BACKOFF_JITTER  # type: ignore[arg-type]
```

### Oczekiwany efekt
- `__init__` body kurczy się o ~18 linii.
- Jitter-parsing logic jest pokryta **5 testami jednostkowymi** bez konieczności konstruować pełnego coordinatora.
- Przygotowany grunt pod przyszły `CoordinatorConfig` dataclass (v2.4.0) — helper to dobry kandydat do `CoordinatorConfig.__post_init__`.

---

## Fix #5 — Uprość property `client` lub udokumentuj indirekcję

**Plik:** `custom_components/thessla_green_modbus/coordinator.py`

**Dowód problemu (linie 298, 365-374):**
```python
        # Connection management
        self._client: Any | None = None
        # ...

    @property
    def client(self) -> Any | None:
        """Return the shared Modbus client."""

        return self._client

    @client.setter
    def client(self, value: Any | None) -> None:
        self._client = value
```

Property nic nie robi poza dostępem do `_client`. Nie ma logowania, walidacji, ani hook'a. Używana jest w wielu miejscach zewnętrznie (scanner, I/O mixin) i wewnętrznie.

**Przed refactorem — sprawdź historię git:**
```bash
cd /home/claude/thesslagreen
git log --all -p -- custom_components/thessla_green_modbus/coordinator.py | \
  grep -A 20 "def client(self)" | head -80
```

**Jeśli widać, że kiedyś była tam logika** (np. lazy-init, logowanie, walidacja):
- Zostaw property, dodaj komentarz wyjaśniający cel.

**Jeśli historia pokazuje, że property było od zawsze proste:**
- Usunąć property, zmienić `_client` na publiczny `client`.

### Krok 5 — uproszczenie (Opcja B, zalecana)

Jeśli `git log` nie pokazuje logiki historycznej w getterze/setterze:

#### SZUKAJ linii 298
```python
        self._client: Any | None = None
```

#### ZASTĄP
```python
        self.client: Any | None = None
```

#### SZUKAJ bloku property+setter (linie ~365-374)
```python
    @property
    def client(self) -> Any | None:
        """Return the shared Modbus client."""

        return self._client

    @client.setter
    def client(self, value: Any | None) -> None:
        self._client = value
```

#### ZASTĄP
*(usuń całkowicie — atrybut `self.client` jest teraz normalnym public attribute)*

Następnie zaktualizuj wszystkie wystąpienia `self._client` w pliku:
```bash
grep -n "self\._client\b" custom_components/thessla_green_modbus/coordinator.py
```

Zamień **każde** `self._client` → `self.client`. Sprawdź również, czy inne pliki nie używają `coordinator._client`:
```bash
grep -rn "\._client\b" custom_components/thessla_green_modbus/ tests/
```

Jeśli znajdziesz wystąpienia w testach/scannerze — zamień na `.client`.

### Krok 5 (alternatywa) — komentarz zamiast usunięcia

Jeśli nie masz pewności, że żaden kod zewnętrzny nie opiera się na secie przez property:

#### ZASTĄP blok property+setter
```python
    @property
    def client(self) -> Any | None:
        """Return the shared Modbus client.

        Property indirection intentionally preserved to support future
        instrumentation (e.g. logging client lifecycle events, lazy
        reconnection) without breaking callers.
        """
        return self._client

    @client.setter
    def client(self, value: Any | None) -> None:
        """Set the shared Modbus client. See getter for rationale."""
        self._client = value
```

### Oczekiwany efekt
- Opcja B: −10 linii kodu, jeden mniej footgun. Minimalne ryzyko breaking change (HA integration nie jest konsumowana jako biblioteka z zewnątrz).
- Opcja A: +5 linii komentarza, czytelny intent. Nic nie zmienia funkcjonalnie.

**Rekomendacja:** Opcja B. Integracja HA jest konsumowana przez platformy entity (`binary_sensor.py`, `climate.py`, itd.), które czytają `coordinator.data`, nie `coordinator.client` jako publiczne API.

---

## Fix #6 — Split `scanner_core.py` (osobny PR, nie w tym release)

**Plik:** `custom_components/thessla_green_modbus/scanner_core.py`

**Dane:** 2512 linii, 103 KB, 30+ metod w jednej klasie `ThesslaGreenDeviceScanner`. Już w v3 audytu był oznaczony jako "do osobnego PR-a".

**Proponowana struktura:**
- `scanner/__init__.py` — re-eksport `ThesslaGreenDeviceScanner`.
- `scanner/core.py` — klasa główna + `__init__` + `scan_device`.
- `scanner/firmware.py` — `_scan_firmware_info`, `_scan_device_identity`.
- `scanner/registers.py` — `_scan_register_batch`, `_scan_named_*`.
- `scanner/io.py` — `_read_input`, `_read_holding`, `_read_coil`, `_read_discrete`, `_read_register_block`, `_read_bit_registers`.
- `scanner/capabilities.py` — `_analyze_capabilities`, `_is_valid_register_value`, `_filter_unsupported_addresses`.

**Ten fix nie jest wdrażany w v2.3.3.** Zostawić jako tracking-issue + oddzielny PR po merdżu 2.3.3.

**Dlaczego nie tutaj:** split tej wielkości wymaga przeniesienia ~10 metod, aktualizacji mixinów `_scanner_*_mixin.py`, regeneracji testów (`test_scanner_coverage.py` — 101 KB!), dużego code review. Wszystko to konkurencyjne z innymi fixami w tym release — warte osobnego ticketu.

---

## Fix #7 — Konsolidacja duplikacji w `services.py` (osobny PR)

**Plik:** `custom_components/thessla_green_modbus/services.py`

**Dane:** 1108 linii, 5 funkcji `_register_*_services`:
- `_register_mode_services` (linia 345)
- `_register_schedule_services` (linia 407)
- `_register_parameter_services` (linia 494)
- `_register_maintenance_services` (linia 687)
- `_register_data_services` (linia 946)

**Potencjalna duplikacja:** każda z nich rejestruje serwisy HA przez `hass.services.async_register(DOMAIN, "name", handler, schema=SCHEMA)`. Warto zweryfikować, czy nie ma powtarzającego się wzorca:
- Walidacja `entity_ids` → coordinator resolution.
- Mapowanie `legacy_entity_id` → `current_entity_id`.
- Obsługa błędów.

### Weryfikacja przed PR-em

```bash
cd /home/claude/thesslagreen
grep -nE "^async def (_register_|_service_handler_)" custom_components/thessla_green_modbus/services.py
grep -cE "_extract_legacy_entity_ids|_get_coordinator_from_entity_id" custom_components/thessla_green_modbus/services.py
```

Jeśli `_extract_legacy_entity_ids` jest wołany >5 razy i otoczony identycznym kodem, jest kandydatem do dekoratora `@service_handler`:

```python
def service_handler(schema: vol.Schema) -> Callable[..., Any]:
    """Decorator: extract entity_ids, resolve coordinator, forward to handler."""
    def decorator(handler: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
        @wraps(handler)
        async def wrapper(call: ServiceCall) -> None:
            entity_ids = _extract_legacy_entity_ids(call.hass, call)
            for entity_id in entity_ids:
                coordinator = _get_coordinator_from_entity_id(call.hass, entity_id)
                if coordinator is None:
                    _LOGGER.warning("No coordinator for %s", entity_id)
                    continue
                await handler(coordinator, call.data)
        return wrapper
    return decorator
```

**Ten fix odłóż do v2.3.4** — wymaga dokładnego audytu rzeczywistej duplikacji (teraz tylko zasygnalizowane, nie zweryfikowane). Osobny PR.

---

## Weryfikacja końcowa

Po zastosowaniu Fixów #1 — #5:

```bash
# Expected: "All checks passed!"
ruff check custom_components/thessla_green_modbus/ tests/ tools/

# Expected: "Success: no issues found in 49 source files"
mypy custom_components/thessla_green_modbus/

# Expected: wszystkie testy przechodzą + 6 nowych (5× _parse_backoff_jitter + 1× cancellation)
pytest tests/ -x -q
```

**Zmiana metryk:**
```
                    v2.3.2     v2.3.3 (target)
ruff:                1 err     0 err
mypy:                0 err     0 err
coordinator.py:     1548 LOC  ~1500 LOC  (−48, Fix #2 + #4a + #5)
_async_update_data:  105 LOC   ~75 LOC   (−30, Fix #2)
test count:        ~1604     ~1610      (+6 nowych)
```

---

## Bump wersji i CHANGELOG

**Plik:** `custom_components/thessla_green_modbus/manifest.json`
```json
"version": "2.3.3",
```

**Plik:** `pyproject.toml`
```toml
version = "2.3.3"
```

**Plik:** `CHANGELOG.md` — dodaj na górze (przed sekcją 2.3.2):
```markdown
## 2.3.3

### Changed
- Removed dead `StrEnum` Python<3.11 compatibility fallback in `registers/schema.py`. Manifest and `pyproject.toml` both require Python ≥3.13, so the fallback was unreachable.
- Extracted `_handle_update_error` helper in coordinator to consolidate 43 lines of duplicated error-handling across three `except` branches of `_async_update_data`.
- Extracted `_parse_backoff_jitter` as a `@staticmethod` in coordinator, making jitter parsing directly unit-testable without constructing a full coordinator.
- Removed redundant property indirection on `coordinator.client` — the getter/setter added no behavior over direct attribute access.

### Fixed
- `_async_update_data` now explicitly handles `asyncio.CancelledError` by closing the transport before re-raising. Prevents the transport from being left in an inconsistent mid-read state when the integration unloads while a read is in progress.

### Added
- Direct unit tests for `_parse_backoff_jitter` covering numeric, string, sequence, and fallback inputs.
- Test guarding against regression of cancellation handling in `_async_update_data`.
```

---

## Notatki końcowe

**Co **nie** wchodzi do v2.3.3 (tracked, odłożone):**

1. **Fix #6** — split `scanner_core.py` (2512 linii → 5-6 modułów). Osobny PR, najlepiej v2.4.0.
2. **Fix #7** — konsolidacja duplikacji w `services.py`. Wymaga głębszego audytu duplikacji zanim da się zaprojektować dekorator `@service_handler`. Osobny PR.
3. **Pełny dataclass `CoordinatorConfig`** — zmiana publicznego API klasy; warto wpiąć w większy refactor konfiguracji (np. razem z config flow options flow schema).
4. **Pokrycie testów** na critical paths `coordinator._read_*_optimized` i `modbus_transport.*`. Wcześniej zasygnalizowane w v1 audytu (cel ≥90%), stan pokrycia nieznany bez uruchomienia `pytest --cov`.

**Co zyskujemy po v2.3.3:**
- Ruff 0 findings (CI zielony 100%).
- Mniej DRY violations w critical path (`_async_update_data`).
- Lepsza obsługa unload/shutdown (cancellation handling).
- Direct-test coverage na jitter parsing (łatwiej zmodyfikować w przyszłości bez breaking `__init__`).
- Mniej footgunów (property bez logiki).

**Ryzyko regresu:** Niskie.
- Fix #1 i Fix #3 są czysto addytywne lub usuwają martwy kod.
- Fix #2 to refactor zachowujący zachowanie (dokładnie te same statystyki, logi, wyjątki — z jedną udokumentowaną zmianą: ujednolicenie `log_message` = `raise_message`).
- Fix #4a to ekstrakcja bez zmiany API.
- Fix #5 ma niskie ryzyko breaking — property `client` może być konsumowane przez scanner_core przez `coordinator.client`, ale to zostaje zwykłym attribute lookup, który działa identycznie.

**Jedyny punkt uwagi:** Fix #2c — niespójność `UpdateFailed` vs `_update_failed_exception`. Przed commitem ustal, czy to jest celowe (np. różny prefix w komunikacie) czy zapomniane przy poprzednim refactorze. Jeśli celowe — udokumentuj; jeśli nie — ujednolicić na `_update_failed_exception`.
