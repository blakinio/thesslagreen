# Airflow Sensor Migration

Recent versions of the integration report supply and exhaust airflow in
**m³/h** instead of percentages. Legacy entities used percentage values and
may have statistics stored in Home Assistant's database.

## Clearing old statistics

1. Stop Home Assistant.
2. Run:
   ```bash
   python3 tools/clear_airflow_stats.py /path/to/config
   ```
   This removes statistics for the old `sensor.supply_flow_rate` and
   `sensor.exhaust_flow_rate` entities.
3. Start Home Assistant – new entities will be created with fresh statistics.

Alternatively, open **Developer Tools → Statistics** in Home Assistant and
manually clear the statistics for these sensors.

## Choosing airflow units

A new option **Airflow unit** is available in the integration options. Select
`m³/h` (default) or `percentage` to have the sensors report airflow in the
preferred unit.
