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

## Migracja z CSV na JSON
Rejestry są obecnie definiowane w pliku JSON `registers/thessla_green_registers_full.json`.
Każdy obiekt w tablicy `registers` zawiera pola:

- `function` – kod funkcji Modbus
- `address_dec` / `address_hex` – adres rejestru
- `name` – unikalna nazwa
- `description` – opis
- `access` – tryb dostępu (`R`/`W`)

Opcjonalnie można zdefiniować `unit`, `enum`, `multiplier`, `resolution` i inne
atrybuty. Aby dodać nowy rejestr, dopisz odpowiedni obiekt do listy `registers`
z zachowaniem kolejności adresów. Format CSV pozostaje jedynie dla kompatybilności
wstecznej – jego użycie zapisuje ostrzeżenie w logach.
