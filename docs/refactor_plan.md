# Refactor Plan

## Cel
Przeprowadzić etapową refaktoryzację do architektury warstwowej bez regresji funkcjonalnych.

## Zakres
- Porządkowanie zależności i odpowiedzialności warstw.
- Stabilizacja testów (unit + HA/PHCC).
- Migracja logiki z modułów legacy do warstw docelowych.

## Poza zakresem
- Zmiany funkcjonalne niezwiązane z refaktoryzacją.
- Rozszerzanie wsparcia o niepotwierdzone urządzenia/protokół.

## Kolejność PR-ów
- PR 1 — test foundation
- PR 2 — platform tests na real HA
- PR 3 — usunięcie platform_stubs.py i uproszczenie conftest.py
- PR 4 — core errors + transport retry
- PR 5 — registers split
- PR 6 — transport package
- PR 7 — core/client.py
- PR 8 — scanner cleanup
- PR 9 — services cleanup
- PR 10 — config flow cleanup
- PR 11 — coordinator package
- PR 12 — cleanup coverage-driven tests

**Nie zaczynać od dużej przebudowy coordinatora, dopóki testy HA/platform nie są stabilne.**

## Ryzyka
- Regresje na granicy coordinator/core.
- Rozjazd zachowania między modelami/firmware.
- Niejednoznaczne reguły dla nieobsługiwanych rejestrów.

## Kryteria akceptacji
- Testy właściwego tieru przechodzą dla każdego etapu.
- Brak naruszeń zakazanych zależności.
- Kompatybilność funkcjonalna utrzymana testami behavioral.
