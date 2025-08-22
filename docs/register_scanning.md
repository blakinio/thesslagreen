# Register scanning and entity mapping

During the initial device scan the integration probes many Modbus register ranges. Some of
the detected addresses represent configuration blocks or multi-register values rather than
single data points. These registers do not map directly to Home Assistant entities.

If a register cannot be read because the device returns a Modbus exception or if the value
fails basic validation, the affected addresses are now recorded and exposed in the
diagnostics. This makes it easier to troubleshoot missing features or firmware
incompatibilities.

Only addresses defined in [entity_mappings.py](../custom_components/thessla_green_modbus/entity_mappings.py)
are exposed as entities by default. The list covers all supported sensors and controls.

Enabling the **force_full_register_list** option creates entities for every discovered
register. This can reveal additional data but may also surface partial values or internal
configuration fields that have no dedicated entity class. Use this option with care and
primarily for debugging or development purposes.

## Dodawanie lub aktualizowanie rejestrów

1. Edytuj plik `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json` dodając nowe obiekty
   lub modyfikując istniejące wpisy.
2. Zachowaj unikalność adresów oraz posortowaną kolejność.
3. Uruchom test walidacyjny:

   ```bash
   pytest tests/test_register_loader.py
   ```

4. Wygeneruj moduł `registers.py` i opcjonalnie sprawdź spójność:

   ```bash
   python tools/generate_registers.py
   python tools/validate_registers.py
   ```

5. Do commitu dodaj zmodyfikowany plik JSON oraz wygenerowany `registers.py`.

## Migracja z CSV na JSON
Rejestry są obecnie definiowane w pliku JSON `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`.
Format CSV jest przestarzały i zostanie usunięty w przyszłych wersjach – jego
użycie zapisuje ostrzeżenie w logach. Każdy obiekt w tablicy `registers` zawiera pola:

- `function` – kod funkcji Modbus
- `address_dec` / `address_hex` – adres rejestru
- `name` – unikalna nazwa
- `description` – opis
- `access` – tryb dostępu (`R`/`W`)

Opcjonalnie można zdefiniować `unit`, `enum`, `multiplier`, `resolution` i inne
atrybuty.

Aby ręcznie przekonwertować istniejący plik CSV:

1. Otwórz plik CSV i odwzoruj kolumny na odpowiednie pola JSON.
2. Dla każdego wiersza utwórz obiekt w `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`.
3. Przekonwertuj adresy na postać dziesiętną i heksadecymalną (`0x...`).
4. Po konwersji uruchom test i narzędzia z sekcji powyżej, aby zweryfikować plik.

Po migracji usuń lub zignoruj plik CSV – integracja korzysta wyłącznie z definicji JSON.
