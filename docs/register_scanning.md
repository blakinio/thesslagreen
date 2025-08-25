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

4. Zaktualizuj tłumaczenia w `custom_components/thessla_green_modbus/translations/en.json` i `pl.json`,
   dodając nowe klucze i usuwając nieużywane. Uruchom `pytest tests/test_unused_translations.py`, aby
   upewnić się, że tłumaczenia są aktualne.
5. Do commitu dodaj zmodyfikowany plik JSON.
6. Jeżeli dany rejestr ma charakter stricte techniczny lub konfiguracyjny i nie powinien być
   eksponowany jako encja, dopisz jego nazwę do stałej `INTENTIONAL_OMISSIONS` w pliku
   `tests/test_register_coverage.py`.

## Oznaczanie rejestrów technicznych

Niektóre wpisy w dokumentacji Modbus opisują pola konfiguracyjne lub pomocnicze,
które nie są potrzebne w Home Assistant. Aby zachować kompletność listy, ale
unikać tworzenia zbędnych encji, ich nazwy należy umieścić w stałej
`INTENTIONAL_OMISSIONS` w teście `tests/test_register_coverage.py`. Dzięki temu
testy będą weryfikować, że wszystkie pozostałe rejestry są odpowiednio
obsługiwane przez integrację.

