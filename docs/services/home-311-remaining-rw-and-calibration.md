# Home 3.11: remaining RW and calibration evidence

Tested unit: AirPack Home 400h series 3 (July 2019), firmware 3.11, base unit
without GWC, duct heater/cooler, external duct filter or Expansion. This extends
the [register-to-HA acceptance](register-diagnostics-and-schedule-temperature.md)
on 2026-10-28. It does **not** establish that every RW command works on this unit.

## Additional physical tests through HA

All tests used the coordinator's existing serialized connection, with fresh raw
reads before/change/restore and actual native entity actions. No second Modbus
client was opened. Fourteen previously excluded settings accepted a distinct
value and returned to their original raw value:

| Registers | Result |
| --- | --- |
| `max_supply_air_flow_rate_gwc`, `max_exhaust_air_flow_rate_gwc` | 150 → 149 → 150 each |
| `nominal_supply_air_flow_gwc`, `nominal_exhaust_air_flow_gwc` | 110 → 111 → 110 each |
| `contamination_coef` | 135 → 136 → 135 |
| `min_gwc_air_temperature`, `max_gwc_air_temperature` | 5 → 5.5 → 5 °C; 25 → 25.5 → 25 °C |
| `gwc_regen_period`, `delta_t_gwc` | 4 → 5 → 4 h; 0 → 0.5 → 0 °C |
| `gwc_regen` | inactive → daily schedule → inactive |
| Four `start/stop_gwc_regen_*_time` words | Each original time + 1 minute, then original time |

HA displayed every changed value. Time entities refreshed after the raw restore;
a later state acquisition confirmed all 15 original entity states. `gwc_off`
requested 1 but read back 0: HA correctly raised `Failed to write register
gwc_off` and remained off. The exact cause of that rejection is not established.
Do not infer a missing physical feature solely from this rejection.

These are **setting-storage tests**, not physical GWC or air-quality actuator
tests: that equipment is absent. A fresh read of all 280 RW definitions returned
269 values and 11 explicit Modbus exceptions. All 265 responding RW definitions
outside the progressing four-word RTC block matched the previous baseline.

The remaining controls include destructive resets, access/product-lock commands,
alarm acknowledgement words whose actual faults are inactive, two firmware-gated
settings, comfort rejected on this unit, and the 11 exception addresses. No
factory reset, product locking, physical safety fault or guessed service command
was performed to inflate acceptance coverage. `filter_change` is a **filter-system
setting on Home**, not an interchangeable AirPack4 replacement command.

## Filter control is not airflow calibration

The manufacturer's [Home protocol, page 5](https://thesslagreen.com/wp-content/uploads/MODBUS_USER_AirPack_Home_08.2021.01.pdf)
defines FC03 address 13:

- 0: normal operation / terminate special procedure;
- 47: external duct-filter pressure-switch check;
- 65: AFC filter check plus external duct-filter check, **from firmware 4.75**.

None of these published descriptions provides the commissioning airflow
calibration start/advance/finish protocol for firmware 3.11. Command 47 is not an
alternative airflow-calibration command. Writing nominal/max flow settings also
does not execute the calibration sequence.

The integration now rejects command 65 on older or unknown firmware before I/O,
across the maintenance service, named write and raw multi-register write paths.
The configuration select omits that unsupported option, preserves its entity ID,
and displays confirmed configuration state rather than an optimistic command.
Stop 0 remains available; this gate does not invent a minimum version for 47.

## Independent implementation review

Sources were inspected at these immutable revisions, including their executable
code rather than relying on a README claim of full support:

| Source | Revision and finding |
| --- | --- |
| [aLAN-LDZ/ThesslaGreen_HA](https://github.com/aLAN-LDZ/ThesslaGreen_HA/tree/5bae9f4a9c5dc540d0e1c8d03a78d1783bfe54cd) | No installer calibration command found in Python/YAML/JSON/Markdown sources. |
| [arypien/ha_thesslagreen_airpack_usb](https://github.com/arypien/ha_thesslagreen_airpack_usb/tree/87a61225cbc7e72c484225f6d6be5f3e7ac44010) | S7 alarm monitoring, no calibration-start implementation found. |
| [voyo/ThesslaGreen-modbus](https://github.com/voyo/ThesslaGreen-modbus/tree/3fbba6f42c77c7fd45995a2e9be78384cfe5c267) | Basic Domoticz controls; tested by author on AirPack4 500h, no calibration-start implementation found. |
| [corapoid/homeassistant-thesslagreen](https://github.com/corapoid/homeassistant-thesslagreen/tree/4435f6f777fb2de868c166303de143ff30e9cc16) | AirPack4 profile uses 13=65 for filter control and 13=0 to stop; explicitly excludes installer calibration. Particle+ commands 42=3 and 4398 status belong to a different device and must not be copied to Home. |
| [Misiu/thessla-green-modbus](https://github.com/Misiu/thessla-green-modbus/tree/7f5917b36aee15b3f081afe46b6cf0ed13cd4a46) | `docs/protocol.md` explicitly excludes factory/installer calibration, access levels, unlocking and filter reset; no hardware verification claimed. |

The manufacturer's older [AirPack Calibrator manual, pages 7–9](https://www.caldo-wentylacja.pl/www/uploaded-files/attachments/instrukcja-obslugi-calibrator-cf.pdf)
describes an installer-password-protected panel sequence: set nominal flows,
stabilize/regulate the installation, then automatic maximum/minimum determination.
It contains no Modbus address/command sequence. Its optional external calibrator
procedure is not proof that this exact Home unit needs that accessory.

The [Home 400h series 3 manual](https://linkair.pl/wp-content/uploads/2024/02/Instrukcja-obslugi-AirPack-Home-400h.pdf)
identifies S7 as calibration blocked by low outdoor temperature, requiring service
reset; it delegates exact conditions to the installation/service manual. No
verified temperature threshold specific to firmware 3.11 was established.

**Open prerequisite for a working HA calibration feature:** a manufacturer- or
hardware-verified Home 3.11 command sequence, required access level, start/advance/
finish states, abort procedure, completion/result readback and operating
conditions. No public implementation inspected supplies this contract. This is
an evidence boundary, not a claim that calibration through any service protocol
is impossible. No working calibration button is claimed or exposed.
