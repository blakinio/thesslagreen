# Dlaczego potrzebna jest migracja `entity_id`

Krótko: **to ograniczenie działania Home Assistant Entity Registry**, a nie integracji.

## Co dzieje się przy zmianie nazwy encji

Integracja tworzy encje na podstawie stabilnego `unique_id` i sugeruje `object_id`.
Jeśli encja o danym `unique_id` już istnieje w rejestrze HA, Home Assistant
**zachowuje dotychczasowe `entity_id`** (nawet jeśli nowa sugerowana nazwa jest inna).

W praktyce oznacza to, że po aktualizacji schematu nazewnictwa integracja może
widzieć nadal stare `entity_id`, dopóki nie zostanie wykonana migracja.

## Dlaczego nie można po prostu „tworzyć poprawnie od nowa”

Dla istniejących encji HA nie tworzy nowego wpisu automatycznie, bo rozpoznaje
je po `unique_id` jako tę samą encję. To celowe zachowanie, które chroni:

- historię encji,
- statystyki,
- automatyzacje i dashboardy powiązane z encją.

Bez migracji mielibyśmy chaos: część encji ze starymi nazwami, część z nowymi,
a czasem duplikaty po ręcznych zmianach.

## Co robi migracja w tej integracji

- mapuje historyczne aliasy do aktualnych nazw,
- sprząta przestarzałe, niemapowalne wpisy (`problem`, `problem_N`),
- utrzymuje możliwie dużą kompatybilność z istniejącymi automatyzacjami.

Dzięki temu po aktualizacji encje przechodzą do aktualnego schematu możliwie
bezboleśnie i przewidywalnie.
