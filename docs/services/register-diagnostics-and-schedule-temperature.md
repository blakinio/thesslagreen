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

On Home firmware 3.11, selecting temporary mode through `mode`, `cfg_mode_1`
or `cfg_mode_2` uses the complete corresponding airflow/temperature activation
triplet. The writer reads and preserves the existing temporary target and
verifies the requested mode word afterwards; a direct single-word echo is
insufficient. The generic mode select does not invent an airflow percentage.

`fan.turn_on` without a percentage resumes the saved operation when the panel
power register is available. It does not replace the saved target with 50% or
move AUTO into temporary mode. An explicit percentage still uses the validated
speed-write path. Devices without a writable panel power register retain the
legacy fallback behavior.

Physical acceptance on the standalone Home 400h firmware 3.11 distinguishes
storage/control confirmation from optional equipment operation. All 357 named
definitions were read: 338 respond and 19 return explicit exceptions. Of 178
native writable-entity cases, 177 passed change/read/display/restore and comfort
mode correctly reports its ignored enable request after the fix. All 56 packed
schedule-temperature set/clear cases passed. Eleven main-action cases, three
clock actions and fan resumption in all three modes passed. The 265 responding
writable definitions outside the progressing RTC block returned to their exact
initial raw values; the original 344 entity IDs remain unchanged.

This does not qualify every possible write to all 280 RW definitions. Seven
reset/security/service definitions were preserved, 60 alarm/type command words
were not physically asserted for blanket reset testing, 15 settings concern
absent accessories, two controls are firmware-gated, eleven RW addresses return
device exceptions, and comfort mode rejects enable. The complete name block and
RTC block are tested as blocks. No undocumented 3.11 calibration command or
physical safety-input fault injection is claimed. Loopback simulations cover
17 transport failures and all 54 mapped individual E/S alarm reports.
