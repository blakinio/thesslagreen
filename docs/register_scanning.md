# Register scanning and entity mapping

During the initial device scan the integration probes many Modbus register ranges. Some of
the detected addresses represent configuration blocks or multi-register values rather than
single data points. These registers do not map directly to Home Assistant entities.

Only addresses defined in [entity_mappings.py](../custom_components/thessla_green_modbus/entity_mappings.py)
are exposed as entities by default. The list covers all supported sensors and controls.

Enabling the **force_full_register_list** option creates entities for every discovered
register. This can reveal additional data but may also surface partial values or internal
configuration fields that have no dedicated entity class. Use this option with care and
primarily for debugging or development purposes.
