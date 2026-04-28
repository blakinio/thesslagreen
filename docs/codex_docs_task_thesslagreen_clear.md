# Zadanie dla Codexa — uporządkowanie dokumentacji `docs/`

Repozytorium:

```text
blakinio/thesslagreen
```

Integracja:

```text
custom_components/thessla_green_modbus
```

Dokumentacja:

```text
docs/
```

---

# 1. Cel zadania

Uporządkuj katalog `docs/` tak, aby dokumentacja pomagała w dalszej refaktoryzacji integracji i nie wprowadzała Codexa w błąd.

Na tym etapie dokumenty `.md` w `docs/` mają służyć głównie jako:

```text
1. kontrakt architektoniczny dla Codexa,
2. zasady refaktoryzacji,
3. lista tego, co wolno i czego nie wolno robić,
4. strategia testowania,
5. minimalna dokumentacja diagnostyki i troubleshooting,
6. źródło linkowane z README bez martwych odnośników.
```

To NIE ma być jeszcze pełna, rozbudowana dokumentacja użytkownika końcowego.

Najważniejsze teraz są dokumenty developerskie / AI-agent docs, które będą pilnować kolejnych zmian.

---

# 2. Bardzo ważne ograniczenia

To zadanie dotyczy wyłącznie dokumentacji.

Możesz zmieniać:

```text
- docs/*.md,
- README.md, ale tylko sekcję linków do dokumentacji, jeśli jest potrzebna aktualizacja.
```

Nie zmieniaj:

```text
- custom_components/thessla_green_modbus/*.py,
- tests/,
- services.yaml,
- manifest.json,
- rejestrów JSON,
- konfiguracji CI,
- struktury kodu produkcyjnego.
```

Nie zgaduj faktów technicznych.

Jeśli nie możesz potwierdzić czegoś z kodu, wpisz:

```text
TODO: verify from code
```

Nie wymyślaj:

```text
- konkretnych modeli urządzeń,
- konkretnych nazw encji,
- konkretnych adresów rejestrów,
- konkretnych wersji firmware,
- konkretnych nazw starych/nowych entity_id,
- zachowania usług, którego nie ma w services.yaml,
- migracji, których nie potwierdza kod.
```

---

# 3. Najważniejsza zasada: bez legacy i bez shimów

W dokumentacji dla Codexa musi być jasno zapisane, że przyszła refaktoryzacja ma iść w stronę nowej struktury bez utrzymywania starego kodu jako warstwy kompatybilności.

Zakazane są:

```text
- legacy modules,
- compatibility shims,
- re-export shims tylko po to, żeby stare importy dalej działały,
- pliki typu *_legacy.py,
- pliki typu *_compat.py,
- adaptery zachowujące starą strukturę importów,
- stare odpowiedniki funkcji pozostawione obok nowych,
- tymczasowe proxy-moduły bez realnej odpowiedzialności.
```

Zasada migracyjna:

```text
1. Przenieś funkcję/klasę do docelowej warstwy.
2. Zaktualizuj wszystkie importy.
3. Przenieś lub popraw testy.
4. Usuń stary moduł/funkcję.
5. Nie zostawiaj shimów.
```

Wyjątek jest dopuszczalny tylko wtedy, gdy Home Assistant wymaga zachowania publicznego API albo istnieje realna migracja użytkowników. Taki wyjątek musi być opisany w komentarzu i w dokumentacji.

---

# 4. Co ma powstać teraz

Na tym etapie utwórz lub zaktualizuj tylko dokumenty naprawdę potrzebne do dalszej pracy.

## Dokumenty wymagane teraz

```text
docs/
├── thesslagreen_architecture.md
├── codex_guidelines.md
├── refactor_plan.md
├── testing_strategy.md
├── diagnostics.md
├── troubleshooting.md
└── register_scanning.md
```

Te pliki są wymagane, bo:

```text
- definiują architekturę,
- pilnują granic warstw,
- opisują zasady dla Codexa,
- opisują kolejność refaktoryzacji,
- opisują strategię testów,
- zastępują martwe linki z README,
- pomagają debugować realne problemy użytkowników.
```

## Dokumenty opcjonalne później

Nie twórz ich teraz, chyba że są już potrzebne przez README albo da się je rzetelnie uzupełnić z kodu:

```text
docs/
├── supported_devices.md
├── supported_functions.md
├── data_updates.md
├── services.md
└── quality_scale.md
```

Te pliki są przydatne, ale mogą poczekać, bo pełna dokumentacja użytkownika końcowego będzie miała większy sens po ustabilizowaniu architektury.

## Dokumenty, których nie tworzyć teraz

Nie twórz teraz:

```text
docs/airflow_migration.md
docs/entity_id_migration.md
```

Powód:

```text
To są dokumenty typowo użytkownikowe/migracyjne.
Jeśli nie ma aktualnej, potwierdzonej migracji i konkretnych nazw encji do opisania, taki dokument może wprowadzać w błąd.
```

Jeżeli README linkuje do tych plików, usuń te linki albo zastąp je linkiem do:

```text
docs/troubleshooting.md
```

lub:

```text
docs/register_scanning.md
```

---

# 5. `docs/thesslagreen_architecture.md`

Jeżeli plik już istnieje, zachowaj go i rozbuduj minimalnie.

Ten plik ma być krótkim overview architektury, nie długim podręcznikiem.

Ma zawierać:

```text
# ThesslaGreen Modbus — Architektura docelowa

## Cel
## Warstwy
## Kierunek zależności
## Krytyczne zasady
## Brak legacy i shimów
## Decyzja migracyjna
```

Wymagane zasady:

```text
- Home Assistant jest cienką warstwą.
- core/transport/registers/scanner nie importują Home Assistant.
- Coordinator nie wykonuje bezpośrednio Modbus I/O.
- Platformy nie dekodują raw register values.
- registers/thessla_green_registers_full.json jest źródłem prawdy.
- Po przeniesieniu funkcji do nowej warstwy usuwamy stary odpowiednik.
- Nie zostawiamy shimów migracyjnych.
```

Opisz warstwy:

```text
1. HA Layer
2. Coordinator
3. Core
4. Registers
5. Scanner
6. Transport
```

Kierunek przepływu:

```text
Platformy HA → Coordinator → Core Client → Registers/Scanner → Transport → pymodbus/socket
```

---

# 6. `docs/codex_guidelines.md`

To jest najważniejszy plik dla Codexa.

Ma być jasny, konkretny i stanowczy.

Wymagana struktura:

```text
# Codex Guidelines

## Cel
## Zasady nadrzędne
## Co wolno robić
## Czego nie wolno robić
## Zakazane zależności
## Brak legacy i shimów
## Docelowa struktura katalogów
## Odpowiedzialność każdej warstwy
## Reguły testów
## Reguły rozmiaru plików
## Kolejność PR-ów
## Checklist przed zakończeniem PR
```

Wpisz twarde reguły:

```text
1. core/, transport/, registers/ i scanner/ nie mogą importować Home Assistant.
2. coordinator/ nie wykonuje bezpośrednio Modbus I/O.
3. platformy HA nie dekodują raw register values.
4. transport/ nie zna nazw rejestrów ThesslaGreen.
5. registers/ nie wykonuje I/O.
6. scanner/ nie zna HA.
7. mappings/ może importować HA, bo to warstwa mapowania encji.
8. Testy platformowe używają real HA/PHCC, bez platform_stubs.py.
9. Testy mają opisywać zachowanie, nie pokrycie linii.
10. Nie optymalizować pod liczbę plików, tylko pod odpowiedzialność modułów.
11. Nie tworzyć legacy modules, compatibility shims ani re-export shimów.
12. Po przepisaniu kodu na nową warstwę usunąć stary odpowiednik.
```

Docelowa struktura produkcyjna do opisania w tym pliku:

```text
custom_components/thessla_green_modbus/
├── __init__.py
├── const.py
├── entity.py
├── diagnostics.py
├── repairs.py
├── sensor.py
├── binary_sensor.py
├── switch.py
├── number.py
├── select.py
├── text.py
├── time.py
├── fan.py
├── climate.py
├── coordinator/
├── core/
├── transport/
├── registers/
├── scanner/
├── mappings/
├── services.py
├── services_schema.py
├── services_helpers.py
├── services_targets.py
├── services_handlers.py
├── config_flow.py
├── config_flow_schema.py
├── config_flow_options.py
├── config_flow_options_form.py
├── config_flow_entry.py
├── config_flow_payloads.py
├── config_flow_runtime.py
├── config_flow_validation.py
└── config_flow_steps.py
```

Checklist PR:

```text
- ruff przechodzi,
- mypy przechodzi, jeśli aktywny,
- pytest dla dotkniętego obszaru przechodzi,
- brak nowych importów HA w core/transport/registers/scanner,
- brak direct Modbus I/O w coordinator/platformach,
- brak testów typu assert result is not None bez znaczenia biznesowego,
- brak martwych shimów,
- brak nowych legacy/compat/proxy modules,
- zachowana kompatybilność config entry/options,
- jeśli zmieniono services.yaml, dodano test i dokumentację.
```

---

# 7. `docs/refactor_plan.md`

Ten plik ma opisać kolejność prac.

Wymagana struktura:

```text
# Refactor Plan

## Cel
## Zakres
## Poza zakresem
## Kolejność PR-ów
## Ryzyka
## Kryteria akceptacji
## Zasada bez legacy/shimów
```

Kolejność PR-ów:

```text
PR 1 — test foundation
PR 2 — platform tests na real HA
PR 3 — usunięcie platform_stubs.py i uproszczenie conftest.py
PR 4 — core errors + transport retry
PR 5 — registers split
PR 6 — transport package
PR 7 — core/client.py
PR 8 — scanner cleanup
PR 9 — services cleanup
PR 10 — config flow cleanup
PR 11 — coordinator package
PR 12 — cleanup coverage-driven tests
```

Ważna zasada:

```text
Nie zaczynać od dużej przebudowy coordinatora, dopóki testy HA/platform nie są stabilne.
```

Dodaj też:

```text
Każdy PR przenoszący kod do nowej warstwy musi usunąć stary odpowiednik.
Nie zostawiać compatibility shimów ani re-export modules.
```

---

# 8. `docs/testing_strategy.md`

Ten plik ma opisać docelowy model testów.

Wymagana struktura:

```text
# Testing Strategy

## Cel
## Test tiers
## Docelowa struktura tests/
## Zakazy
## Dobre nazwy testów
## Co testować real HA
## Co testować mockami
## Co testować pure unit
```

Docelowa struktura:

```text
tests/
├── conftest.py
├── unit/
├── transport/
├── scanner/
├── core/
├── coordinator/
├── ha/
├── platforms/
└── services/
```

Tiery:

```text
Tier 1 — pure unit
- bez HA,
- bez pymodbus,
- bez sieci.

Tier 2 — mock transport / mock pymodbus
- transport,
- scanner,
- core client,
- coordinator z mockowanym clientem.

Tier 3 — real HA / PHCC
- setup/unload/reload,
- config flow,
- options flow,
- reauth flow,
- platforms,
- diagnostics,
- services,
- entity unique_id,
- unavailable state.
```

Zakazy:

```text
- brak platform_stubs.py,
- brak sys.modules patchowania Home Assistant,
- brak testów coverage-driven,
- brak assert result is not None bez znaczenia biznesowego.
```

Przykłady dobrych nazw testów:

```python
test_marks_entities_unavailable_when_device_times_out()
test_reuses_scan_cache_when_device_scan_is_disabled()
test_skips_unsupported_register_after_illegal_address()
test_raises_service_validation_error_for_unknown_register()
test_creates_only_supported_entities_after_scan()
```

---

# 9. `docs/diagnostics.md`

Ten dokument ma pomóc użytkownikowi i developerowi zrozumieć diagnostykę integracji.

Wymagana struktura:

```text
# Diagnostics

## Purpose
## Where to download diagnostics
## What diagnostics include
## What is redacted
## Runtime status
## Connection statistics
## Scan cache
## Failed/skipped registers
## Log level service
## What to attach to a GitHub issue
```

Wpisz jasno:

```text
Diagnostics must not expose passwords, tokens, precise private data, or sensitive network secrets.
```

Nie zgaduj pól diagnostycznych, jeśli nie są potwierdzone w kodzie.

Jeżeli czegoś nie jesteś pewien, użyj:

```text
TODO: verify from code
```

---

# 10. `docs/troubleshooting.md`

Ten dokument ma być praktyczny.

Format obowiązkowy:

```text
## Symptom: Cannot connect to device
### Description
### Resolution

## Symptom: Entities are unavailable
### Description
### Resolution

## Symptom: Some entities are missing
### Description
### Resolution

## Symptom: Timeout / slow polling
### Description
### Resolution

## Symptom: Illegal data address / unsupported register
### Description
### Resolution

## Symptom: Another Modbus client is connected
### Description
### Resolution
```

Nie pisz ogólników typu „check logs” bez konkretu.

Dla każdego symptomu dodaj konkretne kroki:

```text
- co sprawdzić,
- gdzie sprawdzić,
- jaki log może pomóc,
- kiedy zgłosić issue,
- jakie dane dołączyć.
```

---

# 11. `docs/register_scanning.md`

Ten dokument ma opisać skanowanie rejestrów.

Wymagana struktura:

```text
# Register scanning

## Purpose
## Safe scan
## Normal scan
## Deep scan
## Full register list mode
## Scan cache
## Known missing registers
## Unsupported registers
## When to rescan
## Risks of full scan
```

Dodaj jasno:

```text
Full register list mode is diagnostic and may expose entities/registers that are not supported by a given device.
```

Dodaj też:

```text
The final entity set depends on detected capabilities and available registers.
```

Nie obiecuj, że każdy rejestr będzie miał encję.

---

# 12. README.md

Po utworzeniu dokumentów zaktualizuj sekcję dokumentacji w `README.md`.

README ma linkować tylko do istniejących plików.

Na tym etapie linkuj tylko do wymaganych dokumentów:

```text
- Architecture
- Codex Guidelines
- Refactor Plan
- Testing Strategy
- Diagnostics
- Troubleshooting
- Register Scanning
```

Nie linkuj do:

```text
- airflow_migration.md,
- entity_id_migration.md,
- supported_devices.md,
- supported_functions.md,
- data_updates.md,
- services.md,
- quality_scale.md,
```

chyba że faktycznie je utworzysz i są rzetelnie uzupełnione.

Usuń wszystkie martwe linki.

---

# 13. Kryteria akceptacji

Po zakończeniu:

```text
1. README.md linkuje tylko do istniejących plików.
2. docs/thesslagreen_architecture.md nadal istnieje.
3. docs/codex_guidelines.md zawiera twarde reguły architektury.
4. docs/codex_guidelines.md zakazuje legacy modules i compatibility shimów.
5. docs/refactor_plan.md ma kolejność PR-ów.
6. docs/testing_strategy.md zakazuje platform_stubs.py.
7. docs/diagnostics.md opisuje redakcję danych wrażliwych.
8. docs/troubleshooting.md ma format symptom/description/resolution.
9. docs/register_scanning.md wyjaśnia safe/normal/deep/full scan.
10. Nie utworzono dokumentów migracyjnych bez potwierdzonej potrzeby.
11. Nie zmieniono kodu produkcyjnego.
12. Nie zmieniono testów.
13. Nie zmieniono services.yaml ani manifest.json.
```

---

# 14. Walidacja

Ponieważ to jest zadanie dokumentacyjne, minimum:

```bash
python -m compileall -q custom_components/thessla_green_modbus tests tools
ruff check custom_components tests tools
```

Jeśli pełny test suite jest szybki i stabilny:

```bash
pytest tests/ -q
```

Jeśli linter Markdown nie jest skonfigurowany, sprawdź ręcznie:

```text
- linki z README.md,
- nagłówki,
- listy,
- formatowanie Markdown,
- brak martwych odwołań do nieistniejących plików,
- brak dokumentów migracyjnych tworzonych na siłę.
```
