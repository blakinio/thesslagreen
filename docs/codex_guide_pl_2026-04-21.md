# ThesslaGreen Modbus — kompletny guide wykonawczy dla Codexa

**Wersja:** 2.0 (rozszerzona)  
**Data:** 2026-04-21  
**Cel:** jeden obszerny dokument operacyjny zastępujący wcześniejsze audyty, z pełnym kontekstem, priorytetami, bramkami jakości i checklistami wdrożenia.

---

## Spis treści

1. [Kontekst i założenia](#1-kontekst-i-założenia)
2. [Streszczenie wykonawcze](#2-streszczenie-wykonawcze)
3. [Inwentarz problemów (z kategoryzacją)](#3-inwentarz-problemów-z-kategoryzacją)
4. [Szczegółowy audyt obszarów](#4-szczegółowy-audyt-obszarów)
   - 4.1 Runtime vs dokumentacja
   - 4.2 Legacy i PDF coupling
   - 4.3 Modbus transport i zgodność protokołu
   - 4.4 Rejestry i tworzenie encji HA
   - 4.5 Jakość kodu i testowalność
5. [Plan wdrożeniowy dla Codexa (fazy + bramki)](#5-plan-wdrożeniowy-dla-codexa-fazy--bramki)
6. [Backlog zadań (taski atomowe)](#6-backlog-zadań-taski-atomowe)
7. [Komendy walidacyjne (copy/paste)](#7-komendy-walidacyjne-copypaste)
8. [Ryzyka, rollback i strategia PR](#8-ryzyka-rollback-i-strategia-pr)
9. [Definition of Done (DoD)](#9-definition-of-done-dod)
10. [Checklisty operacyjne](#10-checklisty-operacyjne)

---

## 1) Kontekst i założenia

- Integracja jest funkcjonalnie rozbudowana i ma mocną bazę testów, ale występuje dług porządkowy (docs/tooling/lint/legacy paths).
- Celem nie jest „big-bang refactor”, tylko **sekwencyjne PR-y o małym ryzyku**.
- Priorytet: szybkie odzyskanie przewidywalności (spójna dokumentacja, działające narzędzia, zielone gate’y jakości).

**Polityka docelowa:**
1. Brak martwych referencji w dokumentacji.
2. Brak przypadkowego PDF-coupling w procesie walidacji.
3. Jednoznaczny bootstrap testów lokalnych.
4. Modbus hardened (walidacje stricte + testy negatywne).

---

## 2) Streszczenie wykonawcze

### Co działa dobrze
- Warstwa transportu Modbus jest stabilna (retry/backoff, obsługa timeoutów, CRC dla RTU-over-TCP).
- Rejestry są ładowane poprawnie, a encje głównych platform tworzą się poprawnie.
- Istnieje rozbudowany zestaw testów i workflow CI.

### Co wymaga pilnej poprawy
1. **Niespójności docs/runtime** (wersje, stare ścieżki modułów).
2. **Legacy/PDF artefakty** (odwołania do nieistniejących plików, dokumentacja/testy związane z PDF).
3. **Dług jakościowy lint** (`ruff` nie jest zielony).
4. **Punkty utwardzenia Modbus** (strict length/echo/range checks).
5. **Narzędzie `validate_entity_mappings` i część testów climate** wymagają naprawy.

---

## 3) Inwentarz problemów (z kategoryzacją)

## Krytyczne (P1)
- Martwe odwołania do nieistniejących plików w dokumentacji.
- Niespójny przekaz setup/runtime dla contributorów.
- Niedziałające narzędzie developerskie (`tools/validate_entity_mappings.py`).

## Wysokie (P2)
- `ruff` debt i brak pełnej higieny importów/unused.
- Braki strict compliance w RTU-over-TCP (walidacje odpowiedzi).

## Średnie (P3)
- Rozjazdy w testach climate względem aktualnego API.
- Legacy utilities bez jasnej polityki wygaszania.

---

## 4) Szczegółowy audyt obszarów

## 4.1 Runtime vs dokumentacja

### Objawy
- W dokumentacji występują historyczne wzmianki o starych modułach.
- Instrukcje bootstrapu testów lokalnych nie zawsze odzwierciedlają realny setup z CI.

### Skutki
- Contributorzy trafiają na błędy środowiskowe (czas stracony na diagnozy, fałszywe bugi).

### Docelowy stan
- `README_en.md`, `CONTRIBUTING.md`, `tests/README.md` mówią dokładnie to samo co runtime + CI.
- Każda komenda w docs jest wykonywalna bez „domyślania się” brakujących kroków.

---

## 4.2 Legacy i PDF coupling

### Objawy
- W repo były/pozostały odwołania do starych ścieżek (np. `scanner_core.py`, `entity_mappings.py`).
- W dokumentacji/testach pojawia się walidacja oparta o PDF producenta i martwe komendy do nieistniejących plików.

### Skutki
- Chaos poznawczy i niespójny proces walidacji.
- Niestabilność automatyzacji, jeśli workflow zależy od artefaktów spoza repo.

### Docelowy stan
- Walidacja oparta na JSON/schema/rules w repo, bez PDF jako źródła prawdy.
- Legacy izolowane w `docs/legacy` / `tools/legacy` lub całkowicie usunięte (zależnie od decyzji zespołu).

---

## 4.3 Modbus transport i zgodność protokołu

### Co jest poprawne
- Retry/backoff/cancellation są obsłużone.
- Dla RTU-over-TCP jest CRC i podstawowa walidacja ramek.
- Grouping i limity są dostosowane do profilu urządzenia.

### Co utwardzić
1. **FC03/FC04:** wymusić `byte_count == count * 2`.
2. **FC06/FC16:** walidować echo odpowiedzi (adres, wartość/ilość).
3. **Range guardy:** fail-fast dla nieprawidłowych `count/qty` na granicy transportu.
4. **`slave_id` consistency:** ujednolicić semantykę walidacji, aby uniknąć niejednoznacznych przypadków.

### Dlaczego to ważne
- Te poprawki są tanie, a zamykają klasę „cichych” błędów protokołu.

---

## 4.4 Rejestry i tworzenie encji HA

### Stan
- Loader/schema/map rejestrów: działa poprawnie.
- Integracyjne tworzenie encji dla głównych platform: działa poprawnie.

### Znane problemy poboczne
- Testy `climate` nieaktualne względem API koordynatora.
- `tools/validate_entity_mappings.py` wymaga aktualizacji importów.

### Docelowy stan
- Narzędzia developerskie działają out-of-the-box.
- Testy platform mają spójny kontrakt z aktualnym API.

---

## 4.5 Jakość kodu i testowalność

### Stan
- `ruff` raportuje naruszenia do naprawy.
- Lokalny bootstrap testów wymaga dopięcia i jasnej instrukcji.

### Cel
- Zielone lint gate’y i stabilny lokalny flow testów od pierwszego uruchomienia.

---

## 5) Plan wdrożeniowy dla Codexa (fazy + bramki)

## Faza 1 — Docs/Legacy/PDF cleanup (P1)

### Zakres
- Ujednolicenie docs do runtime/CI.
- Usunięcie martwych referencji i PDF-coupling w docs.
- Naprawa broken developer tool paths/imports.

### Bramki F1
- Brak odwołań do nieistniejących ścieżek.
- Dokumentacja bootstrapu testów = rzeczywiste kroki uruchomieniowe.

---

## Faza 2 — Lint & test bootstrap hygiene (P1/P2)

### Zakres
- `ruff --fix` + ręczne poprawki.
- Dopięcie instrukcji instalacji zależności testowych zgodnie z CI.

### Bramki F2
- `ruff check custom_components tests tools` = 0.
- `python -m compileall -q ...` = PASS.

---

## Faza 3 — Modbus hardening (P2)

### Zakres
- Walidacje strict length/echo/range w transporcie.
- Testy negatywne na uszkodzone/niezgodne odpowiedzi.

### Bramki F3
- Kompletny zestaw testów Modbus = PASS.
- Brak regresji w zachowaniu komunikacji.

---

## Faza 4 — Register/entity gate + narzędzia (P1/P3)

### Zakres
- Potwierdzenie loader/schema/map + entity setup.
- Naprawa `tools/validate_entity_mappings.py`.
- Naprawa/regeneracja testów climate pod obecny API kontrakt.

### Bramki F4
- Rejestry + encje + tooling = PASS.
- Climate tests wracają do stanu przewidywalnego (pass lub świadomie oznaczone/odseparowane).

---

## 6) Backlog zadań (taski atomowe)

## DOK-01
- Zaktualizuj `README_en.md` i usuń historyczne ścieżki.
- AC: brak starych ścieżek, poprawne wersje.

## DOK-02
- Zaktualizuj `CONTRIBUTING.md` i `tests/README.md` do realnego bootstrapu.
- AC: nowy contributor odpala testy bez dodatkowych pytań.

## LEG-01
- Usuń martwe komendy PDF tooling z docs.
- AC: każda komenda z docs istnieje i działa.

## TOOL-01
- Napraw `tools/validate_entity_mappings.py` pod aktualny moduł mapowań.
- AC: skrypt zwraca exit 0 w zdrowym stanie.

## LINT-01
- Uruchom `ruff --fix` i zamknij ręcznie resztę.
- AC: `ruff check ...` zielony.

## MOD-01
- Dodaj check `byte_count == expected` w RTU-over-TCP.
- AC: nowe testy negatywne i pozytywne PASS.

## MOD-02
- Dodaj walidację echa FC06/FC16.
- AC: błędne echo -> wyjątek, poprawne echo -> sukces.

## MOD-03
- Dodaj guardy zakresów `count/qty`.
- AC: out-of-range natychmiast fail-fast.

## CFG-01
- Ujednolić walidację `slave_id` tam, gdzie wykorzystywany jest request/response.
- AC: spójny zakres i test regresyjny.

## TST-01
- Napraw testy climate pod aktualny kontrakt API.
- AC: testy nie odwołują się do nieistniejących helperów.

---

## 7) Komendy walidacyjne (copy/paste)

```bash
# A) Szybki sanity
python -m compileall -q custom_components/thessla_green_modbus tests tools
ruff check custom_components tests tools

# B) Modbus
pytest -q \
  tests/test_modbus_transport.py \
  tests/test_modbus_transport_close.py \
  tests/test_modbus_helpers.py \
  tests/test_rtu_transport.py \
  tests/test_raw_rtu_over_tcp_transport.py \
  tests/test_multi_register_write.py \
  tests/test_chunking.py \
  tests/test_group_reads.py \
  tests/test_group_reads_max_size.py \
  tests/test_backoff.py \
  tests/test_read_cancellation.py

# C) Rejestry + encje
python tools/validate_registers.py
python tools/validate_entity_mappings.py
pytest -q \
  tests/test_integration.py \
  tests/test_loader_integration.py \
  tests/test_force_full_register_list_integration.py \
  tests/test_sensor_platform.py \
  tests/test_binary_sensor.py \
  tests/test_select.py \
  tests/test_number.py \
  tests/test_switch.py

# D) (po fixach) climate
pytest -q tests/test_climate.py
```

---

## 8) Ryzyka, rollback i strategia PR

### Ryzyka
1. Mieszanie zmian funkcjonalnych i porządkowych w jednym PR.
2. Niezauważona zmiana zachowania podczas „niewinnych” poprawek lint.
3. Nadmierne czyszczenie legacy bez planu migracji użytkowników.

### Rollback
- Każda faza jako osobny commit/PR.
- Dla Modbus hardening: test-first + feature branch + rollback 1-commit.

### Zalecany podział PR
1. **PR-A:** docs + legacy/PDF cleanup (bez runtime).
2. **PR-B:** lint/hygiene (bez logiki).
3. **PR-C:** Modbus hardening (logika + testy).
4. **PR-D:** tooling/climate test alignment.

---

## 9) Definition of Done (DoD)

- [ ] Jeden spójny, aktualny zestaw docs bez martwych referencji.
- [ ] Brak przypadkowego PDF-coupling w walidacji (lub jawnie opisana decyzja projektowa).
- [ ] Zielony lint i compile checks.
- [ ] Modbus hardening wdrożony + testy negatywne.
- [ ] Rejestry i encje HA potwierdzone testami.
- [ ] Narzędzia developerskie uruchamiają się bez błędów importu.

---

## 10) Checklisty operacyjne

## Checklista „przed startem pracy Codexa”
- [ ] Zsynchronizowany branch.
- [ ] Środowisko testowe gotowe.
- [ ] Ustalony zakres fazy (tylko jedna faza na PR).

## Checklista „przed otwarciem PR”
- [ ] Komendy z sekcji 7 uruchomione.
- [ ] Wyniki i odchylenia wpisane do opisu PR.
- [ ] Brak zmian poza zakresem fazy.

## Checklista „po merge”
- [ ] Aktualizacja guide’a (jeśli zmienił się stan).
- [ ] Zamknięcie tasków fazy.
- [ ] Decyzja o kolejnej fazie.

---

## Notatka końcowa

Ten guide jest celowo obszerny: ma zastąpić rozproszone audyty i być **operacyjnym runbookiem** dla Codexa i maintainera. Jeśli potrzebujesz, mogę od razu rozpocząć **Fazę 1** i dostarczyć pierwszy PR porządkowy według powyższego podziału.
