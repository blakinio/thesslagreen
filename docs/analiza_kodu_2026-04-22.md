# Dogłębna analiza kodu — ThesslaGreen Modbus (2026-04-22)

## 1) Zakres i metoda

Przeanalizowałem strukturę repozytorium, kluczowe moduły runtime, konfigurację narzędzi oraz testy.
Analiza obejmuje:

- architekturę integracji Home Assistant,
- złożoność i utrzymywalność kodu,
- odporność na błędy i obserwowalność,
- ergonomię developmentu i uruchamialność testów,
- plan usprawnień (krótko-, średnio- i długoterminowy).

## 2) Szybki obraz projektu

Projekt jest dojrzały funkcjonalnie (duży zakres modułów i usług), ma szerokie pokrycie testami, ale posiada wyraźne „hotspoty” utrzymaniowe:

- bardzo duże pliki (1000+ linii) w krytycznych obszarach,
- bardzo długie funkcje odpowiedzialne za wiele rzeczy naraz,
- powtarzalne wzorce retry/backoff i obsługi wyjątków w kilku warstwach,
- część walidacji/testów jest trudna do uruchomienia bez pełnego środowiska HA.

## 3) Mocne strony

1. **Modułowość domenowa**
   - Kod jest podzielony na warstwy: transport, scanner, coordinator, services, config flow.
   - To dobry fundament do dalszego refaktoru inkrementalnego.

2. **Dojrzałe podejście do jakości**
   - Rozbudowany zestaw testów (94 pliki testowe).
   - Skonfigurowane narzędzia: ruff, mypy, pytest, coverage.

3. **Praktyczne mechanizmy operacyjne**
   - Rozbudowana diagnostyka i serwisy utrzymaniowe.
   - Obsługa kilku trybów połączeń i scenariuszy komunikacji Modbus.

## 4) Kluczowe ryzyka techniczne

### R1. Nadmierna koncentracja logiki w „mega-modułach”

Największe pliki:

- `coordinator.py` — 1255 linii,
- `config_flow.py` — 1071 linii,
- `scanner/core.py` — 1032 linii,
- `modbus_transport.py` — 895 linii.

**Skutek biznesowy:** wolniejsze wdrażanie zmian, większe ryzyko regresji, trudniejszy onboarding.

### R2. Zbyt długie funkcje (wysokie ryzyko defektów)

Przykłady:

- `_extend_entity_mappings_from_registers` — 245 linii,
- `_call_modbus` — 163 linii,
- `_read_with_retry` — 156 linii,
- kilka handlerów serwisów >130 linii.

**Skutek:** funkcje łączą wiele odpowiedzialności (walidacja, logika domenowa, retry, logowanie), co utrudnia testowanie jednostkowe i bezpieczny refaktor.

### R3. Rozproszona polityka błędów i retry/backoff

Retry/backoff i transformacja wyjątków istnieją równolegle m.in. w:

- warstwie transportu,
- coordinatorze (IO),
- config flow.

**Skutek:** niespójne zachowanie na granicznych awariach (timeout/cancel/IO), większa trudność diagnozowania „flaky” problemów.

### R4. Potencjalnie kosztowne ładowanie danych przy imporcie

`REGISTER_DEFS = {r.name: r for r in get_all_registers()}` jest budowane przy imporcie modułu koordynatora.

**Skutek:** niepotrzebny koszt startupu/importu oraz większa sztywność inicjalizacji (szczególnie w testach i narzędziach).

### R5. Ryzyko dryfu przy ręcznym unload usług

Lista usług do `async_remove` jest utrzymywana ręcznie.

**Skutek:** łatwo o niespójność „registered vs unloaded” po dodaniu nowej usługi.

### R6. Tarcie developerskie w lokalnym uruchomieniu testów

W aktualnym środowisku testy nie uruchamiają się bez `homeassistant`, a narzędzia walidacyjne bez `pydantic`.

**Skutek:** podniesiony koszt wejścia i wolniejszy feedback loop dla contributorów.

## 5) Priorytetyzowany plan usprawnień

## P1 (najbliższe 1–2 sprinty): szybkie zyski

1. **Wydzielenie warstwy `error_policy` + `retry_policy`**
   - Jeden moduł z regułami klasyfikacji błędów i strategią retry.
   - Używany przez transport, coordinator i config flow.

2. **Refaktor najdłuższych funkcji metodą „extract function”**
   - Cel: funkcje < 60–80 linii.
   - Każdy wydzielony krok z osobnym testem jednostkowym.

3. **Rejestr usług oparty o pojedyncze źródło prawdy**
   - Jedna lista/dict opisująca usługi (rejestracja + unload).
   - Eliminuje dryf i duplikację.

4. **Lazy loading definicji rejestrów**
   - `REGISTER_DEFS` budowane na żądanie (cache + invalidacja testowa).

## P2 (2–4 sprinty): redukcja kosztu utrzymania

1. **Podział `coordinator.py` na mniejsze moduły domenowe**
   - np. `coordinator_bootstrap.py`, `coordinator_reads.py`, `coordinator_writes.py`, `coordinator_health.py`.

2. **Podział `config_flow.py` na etapy i walidatory**
   - schematy wejścia, walidacja transportu, autowykrywanie, mapowanie options.

3. **Wprowadzenie kontraktów przez `Protocol`**
   - interfejsy dla transportu i scannera, aby uprościć mocking i testy.

## P3 (4+ sprintów): skalowalność i niezawodność

1. **Ujednolicona telemetria błędów i retry**
   - wspólne liczniki timeout/reconnect/retry/failure reason.

2. **Testy scenariuszowe awarii transportu**
   - test matrix dla TCP/RTU/TCP-RTU + cancel + timeout + half-open connection.

3. **Automatyczny „maintainability gate” w CI**
   - limity dla długości funkcji/pliku i alarmy przy ich przekroczeniu.

## 6) Konkretne rekomendacje implementacyjne

### A. Wspólna polityka błędów

Utworzyć moduł `error_policy.py`, np.:

- `classify_exception(exc) -> ErrorKind`
- `should_retry(kind, attempt, max_attempts) -> bool`
- `next_backoff(attempt, base, max, jitter) -> float`

Następnie usunąć lokalne rozgałęzienia w transport/coordinator/config_flow i zastąpić wywołaniami policy.

### B. Refaktor „long methods first”

Najpierw funkcje > 140 linii; każdą dzielić na kroki:

- `validate_input(...)`
- `prepare_request(...)`
- `execute_with_retry(...)`
- `normalize_response(...)`
- `emit_diagnostics(...)`

### C. Jedno źródło prawdy dla usług

Wprowadzić strukturę np. `SERVICE_SPECS`, która zawiera:

- nazwę usługi,
- schema,
- handler,
- opcjonalne flagi/warunki.

`async_setup_services` iteruje po `SERVICE_SPECS`, a `async_unload_services` usuwa dokładnie te same nazwy.

### D. Usprawnienie developer experience

- Dodać „minimalne” środowisko testowe (np. `requirements-test-min.txt`) dla walidatorów i narzędzi bez pełnego HA.
- Dodać komendę smoke-check (np. `python tools/validate_registers.py`) do pre-commit/CI, wraz z jasnym komunikatem zależności.

## 7) Proponowany plan wykonania (praktyczny)

### Tydzień 1
- Wspólna polityka retry/błędów + testy jednostkowe.
- Refaktor 2 najdłuższych funkcji.

### Tydzień 2
- Single source of truth dla usług.
- Lazy loading rejestrów + testy regresji.

### Tydzień 3–4
- Podział `config_flow.py` i `coordinator.py` bez zmiany API publicznego.
- Dodanie maintainability gate do CI.

## 8) Oczekiwany efekt

Po wdrożeniu planu:

- niższy koszt modyfikacji krytycznych ścieżek (config + IO),
- mniejsze ryzyko regresji przy zmianach funkcjonalnych,
- spójniejsze zachowanie na błędach transportu,
- szybszy onboarding i krótszy czas dostarczenia poprawek.

## 9) Status realizacji zaleceń (aktualizacja)

Wdrożone elementy z priorytetu P1:

1. **Wspólna polityka błędów/retry/backoff**
   - Dodano współdzieloną warstwę `error_policy` używaną przez runtime config flow i transport Modbus.
2. **Refaktor „long methods first”**
   - Rozbito `_call_modbus` na mniejsze funkcje pomocnicze (normalizacja argumentów, wybór kwarg `slave/device_id/unit`, logowanie request/response, wywołanie).
3. **Single source of truth dla usług**
   - Rejestracja i unload usług działają na wspólnej specyfikacji grup usług.
4. **Lazy loading definicji rejestrów**
   - Definicje rejestrów są ładowane przez cache (`lru_cache`) na żądanie, zamiast przy imporcie.

Weryfikacja:
- testy jednostkowe dla zmodyfikowanych ścieżek (`modbus_helpers`, `modbus_transport`, `config_flow_helpers`, `services`, `coordinator_coverage`) przechodzą,
- lint (`ruff`) przechodzi dla zmienionych plików.

Elementy P2 wdrożone częściowo:
- dodano kontrakty `Protocol` dla warstwy usług/skanera (`ScannerFactory`, `ScannerProtocol` i typy callable zależności), co upraszcza mocking i stabilizuje interfejsy.
