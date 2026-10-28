# Confirmed reads and schedule temperatures

`thessla_green_modbus.read_register_diagnostics` reads 1–32 named definitions
through the selected device's existing coordinator connection. Select exactly one
device or one of its entities. The action returns a response and performs no
writes. It does not change the normal polling cache.

```yaml
action: thessla_green_modbus.read_register_diagnostics
target:
  entity_id: climate.my_airpack
data:
  names: [s_17, e_252, setting_summer_mon_1]
response_variable: confirmed
```

Each result contains the function, address, complete raw word/bit list, decoded
value and status. `ok` means a complete response decoded successfully.
`modbus_exception` includes the device's exception code; it is distinct from
`indeterminate` transport failures, `incomplete_response` and `decode_error`.
The response also includes `writes_sent: 0`. Home RTC words 0–3 and lock-date
words 7–9 are read together even when only one member was requested. Multiword
names and serials use their complete definition length. Unknown names are
rejected before any device reads. This diagnostic action does not make a
reserved register's control command supported.

Each `select.*setting_*` entity exposes confirmed `airflow_percentage`,
`temperature_c` and `temperature_unset` attributes. A schedule setting is a
packed airflow/temperature word; changing airflow preserves its temperature.
An unset temperature has `temperature_c: null` and `temperature_unset: true`.

`set_airflow_schedule` (and its compatibility alias `set_intensity`) can set or
clear that temperature. A complete enabled slot requires its start time and
airflow. Omitting `temperature` preserves the current temperature. Pass
`clear_temperature: true` to restore the controller's TT=0 unset marker.
`temperature` and `clear_temperature: true` are mutually exclusive.
Weekdays accept both plain names such as `monday` and the existing selector
values such as `thessla_green_modbus.day_monday`; both reach the same device slot.

```yaml
action: thessla_green_modbus.set_airflow_schedule
target:
  entity_id: climate.my_airpack
data:
  season: summer
  day: monday
  period: 1
  start_time: '08:00'
  airflow_rate: 50
  temperature: 20.5
```

To clear this temperature, keep the other slot fields, remove `temperature`
and add `clear_temperature: true`. Temperature values use 0.5 °C steps in the
documented 10–45 °C range. Reading/storing a temperature does not establish
that optional heating/cooling equipment is installed.

Clock synchronization uses Home Assistant's configured local timezone. The
verified `sync_device_clock` action fails when the controller does not return
the RTC words after a write; an acknowledged write without readback is not a
confirmed synchronization.

For allow-listed single-word operational controls, a successful readback is
also compared with the encoded requested value. If the device acknowledges a
write but returns a different value, the coordinator publishes the actual
confirmed state and reports failure. Number/switch entities therefore cannot
replace that confirmed state with a successful optimistic setpoint after an
ignored command. Reset/trigger words keep their separate command semantics.
