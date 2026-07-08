# Real-Device Validation Report

**Status: PARTIAL real-device validation — latest HA log evidence recorded**

> This document records evidence collected from a real ThesslaGreen AirPack 4 device running
> through Home Assistant and the `thessla_green_modbus` custom integration. It must not be
> treated as a full quality-scale sign-off until all manual service/UI checks in the release gate
> are completed and the exact installed integration commit is recorded.

---

## 1. Current validation status

| Item | Status | Evidence |
|------|--------|----------|
| Overall validation | PARTIAL PASS | Real HA logs confirm setup, scan-cache startup, service registration, basic read path, and fan writes. UI screenshots/service evidence still pending. |
| Quality scale gate | Bronze | Keep bronze until formal real-device evidence is complete and signed off. |
| Latest post-refactor runtime smoke | PARTIAL PASS | 2026-07-08 HA log after the read-back / connection / read-helper refactors shows clean setup and successful writes. |
| Config-flow scan cache | PASS | `Using config-flow scan cache` in latest log. |
| TCP connection | PASS | `192.168.3.12:8899`, `slave_id=10`, TCP selected. |
| Services registered | PASS | `ThesslaGreen Modbus services registered successfully`. |
| Basic write path | PARTIAL PASS | `air_flow_rate_manual` writes to 50.0 and 30.0 succeeded. Full fan/UI behaviour still needs manual confirmation. |
| Targeted read-back allow-list (#1745) | PARTIAL PASS | No `transaction_id mismatch` or false disconnect after writes in latest log. Specific allow-listed number/select/switch tests still pending. |
| Connection helper consolidation (#1748) | PARTIAL PASS | Latest log shows setup and scan-cache startup after the consolidation. Longer runtime validation still pending. |
| Read helper consolidation (#1750) | PARTIAL PASS | Latest log shows scanner/read batches completing and detected capabilities. Longer polling validation still pending. |
| CI / Python 3.13 validation | PASS on CI | Latest runtime refactor CI was green on Python 3.13 before this docs-only update. |
| Vendor coverage | PASS by tool | `compare_airpack4_vendor_coverage.py` reports 0 missing vendor registers in CI/validation. |

---

## 2. Environment

| Item | Value |
|------|-------|
| Device model | ThesslaGreen AirPack 4 (user-reported) |
| Firmware version | Unknown / not exposed by this device scan; non-critical on this unit |
| Connection type | TCP / Auto-selected by config-flow scan |
| Host / Port / Slave ID | `192.168.3.12` / `8899` / `10` |
| Scan interval | `30s` |
| max_registers_per_request | `16` (confirmed in HA options screenshot, 2026-07-08) |
| Deep scan | OFF / not required for normal validation |
| force_full_register_list | Not enabled in available evidence |
| Home Assistant OS | 17.3 confirmed in earlier 2026-06-09 `validate_known_registers` session |
| Home Assistant Core | 2026.6.1 confirmed in earlier 2026-06-09 `validate_known_registers` session; exact version for 2026-07-08 log not present in exported snippet |
| Integration commit actually installed in HA | Not proven by log. User context says the log was captured after the refactor series; treat as post-#1745/#1748/#1750 evidence, but keep exact commit pending until HA/HACS shows it. |
| Current repository main when this document was updated | `c1e188656921e897e4604625a1fb4b229473bfad` (merge #1749; workflow-only after #1750) |
| Latest evidence source | `home-assistant_2026-07-08T08-27-09.883Z.log` |

---

## 3. Latest HA log evidence — 2026-07-08

Provided file:

```text
home-assistant_2026-07-08T08-27-09.883Z.log
```

Relevant setup/read/write lines:

```text
2026-07-08 10:25:03.654 DEBUG Read input registers 0-0: [3]
2026-07-08 10:25:04.028 DEBUG Expected missing input register (code 2): input registers 4-4
2026-07-08 10:25:04.028 DEBUG Failed to read firmware version registers: missing version_patch (4)
2026-07-08 10:25:20.102 INFO  Detected 14 capabilities
2026-07-08 10:25:20.102 DEBUG Skipping expected optional firmware registers 4-4 (exception code 2)
2026-07-08 10:26:19.305 INFO  Initializing ThesslaGreen device: ThesslaGreen via Modbus TCP (Auto) (192.168.3.12:8899) (slave_id=10, scan_interval=30s)
2026-07-08 10:26:19.307 INFO  Setting up ThesslaGreen coordinator for 192.168.3.12:8899 via TCP
2026-07-08 10:26:19.309 INFO  Using config-flow scan cache
2026-07-08 10:26:34.375 INFO  Entity skipped due to capability: duct_supply_temperature (sensor_duct_supply_temperature not supported)
2026-07-08 10:26:34.375 INFO  Entity skipped due to capability: gwc_temperature (sensor_gwc_temperature not supported)
2026-07-08 10:26:50.252 INFO  ThesslaGreen Modbus services registered successfully
2026-07-08 10:26:50.252 INFO  ThesslaGreen Modbus integration setup completed successfully
2026-07-08 10:26:50.288 INFO  Successfully wrote 50.0 to register air_flow_rate_manual
2026-07-08 10:26:50.584 INFO  Successfully wrote 30.0 to register air_flow_rate_manual
```

Negative checks from the same log:

| Check | Result |
|------|--------|
| `transaction_id mismatch` | Not observed |
| `Modbus transport is not connected` | Not observed |
| `Traceback` | Not observed |
| `custom_components.thessla_green_modbus` ERROR | Not observed |
| Blocking I/O warning for ThesslaGreen | Not observed |
| False unsupported-register spam | Not observed; firmware `version_patch` is logged as expected optional |

Warnings / notes in the same exported log:

| Warning | Interpretation |
|---------|----------------|
| `Referenced entities number.thesslagreen_air_flow_rate_manual are missing or not currently available` | Likely HA automation/script/dashboard timing or stale entity reference during startup. Not emitted by the integration. Needs user-side HA automation/entity check if it repeats after startup. |
| `Setup of sensor platform thessla_green_modbus is taking over 10 seconds` | Non-fatal; setup later completed successfully. Expected with a large entity set. |
| `homeassistant.components.cloud.google_config` Device ID warnings | Unrelated to ThesslaGreen. |
| ESPHome Dallas checksum warning | Unrelated to ThesslaGreen. |

Interpretation:

- The post-refactor startup path is clean in the captured log.
- Read batches/scanner calls complete and detect capabilities.
- Config-flow scan cache is used for setup.
- Services are registered.
- Basic write path works for `air_flow_rate_manual`.
- No evidence of the historical `transaction_id mismatch` problem.
- No evidence of false `Modbus transport is not connected` during setup/write.
- Exact installed integration commit is still not proven by the log and must be captured separately.

---

## 4. Earlier real-device evidence

### 4.1 HA log export — 2026-05-30

Provided file:

```text
home-assistant_2026-05-30T10-48-08.801Z.log
```

Relevant setup lines:

```text
2026-05-30 12:44:03.898 INFO  verify_connection: connecting to 192.168.3.12:8899 (mode=tcp, timeout=10)
2026-05-30 12:44:14.761 INFO  verify_connection: auto-selected Modbus transport tcp for 192.168.3.12:8899
2026-05-30 12:44:41.941 INFO  Detected 14 capabilities
2026-05-30 12:45:20.746 INFO  Initializing ThesslaGreen device: ThesslaGreen via Modbus TCP (Auto) (192.168.3.12:8899) (slave_id=10, scan_interval=30s)
2026-05-30 12:45:20.751 INFO  Using config-flow scan cache
2026-05-30 12:46:00.838 INFO  ThesslaGreen Modbus services registered successfully
2026-05-30 12:46:00.838 INFO  ThesslaGreen Modbus integration setup completed successfully
```

Known expected notes from this older log:

- Firmware/model registers may be unavailable on this unit and are non-critical.
- A scanner cancellation on `input_registers 0-0` was observed once, but scan/setup continued.
- No ThesslaGreen traceback, `transaction_id` mismatch, blocking I/O warning, or false transport-disconnected error was observed.

### 4.2 `validate_known_registers` evidence — 2026-06-09

Real-device service result observed after PRs #1709/#1711 on HA OS 17.3 / HA Core 2026.6.1:

```text
validate_known_registers started for climate.rekuperator_climate_control: batch=16, delay=100ms
validate_known_registers completed for climate.rekuperator_climate_control: supported=338, missing=19, by_type={'input_registers': 4, 'holding_registers': 15}
```

Stable result:

| Metric | Value |
|--------|-------|
| supported_count | 338 |
| missing_count | 19 |
| missing_by_type / input_registers | 4 |
| missing_by_type / holding_registers | 15 |
| retried_individual_count | 62 |

No `transaction_id` mismatch was observed during or after the service call.

`validate_known_registers` uses the coordinator's active Modbus connection under `_write_lock`. It does not open a second Modbus connection and is the preferred real-device register classification method. `scan_all_registers` is development/offline diagnostics and must not be used as routine validation.

### 4.3 Expected missing / optional registers on tested device

These registers should **not** be removed from the register map — they may be valid on other firmware/hardware variants.

#### Missing input_registers (4)

| Register | Classification | Notes |
|----------|----------------|-------|
| `compilation_days` | optional_firmware_metadata | Legacy firmware does not expose build timestamp |
| `compilation_seconds` | optional_firmware_metadata | Legacy firmware does not expose build timestamp |
| `version_patch` | optional_firmware_metadata | Legacy firmware exposes only version_major/version_minor |
| `water_removal_active` | optional_feature | Water removal feature not present on this unit |

#### Missing holding_registers (15)

| Register | Classification | Notes |
|----------|----------------|-------|
| `cfg_post_heater_mode` | hardware_gated | Post-heater capability absent on this hardware |
| `post_heater_on` | hardware_gated | Post-heater capability absent on this hardware |
| `cfgszf_fn_new` | expansion_or_service | Expansion/service firmware register |
| `cfgszf_fw_new` | expansion_or_service | Expansion/service firmware register |
| `exp_version` | expansion_or_service | Expansion module not present |
| `filter_exhaust_date_limit_get` | newer_firmware_api | Filter date API not available on this firmware |
| `filter_supply_date_limit_get` | newer_firmware_api | Filter date API not available on this firmware |
| `uart_0_baud` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_0_id` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_0_parity` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_0_stop` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_baud` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_id` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_parity` | internal_service_uart | Internal UART configuration; inaccessible on normal device |
| `uart_1_stop` | internal_service_uart | Internal UART configuration; inaccessible on normal device |

---

## 5. Manual validation checklist

> Do not mark any row PASS without HA log evidence, screenshot evidence, or a service response.

| # | Check | Expected result | Current result | Evidence |
|---|-------|-----------------|----------------|----------|
| 1 | Restart/reload integration | Setup completes successfully | PASS | 2026-07-08 log: `setup completed successfully` |
| 2 | No traceback during setup | No `Traceback` / coordinator exception | PASS | 2026-07-08 log negative search |
| 3 | Config-flow scan cache | Cache used at setup | PASS | 2026-07-08 log: `Using config-flow scan cache` |
| 4 | Services registered | Services available after setup | PASS | 2026-07-08 log: `services registered successfully` |
| 5 | Normal scan detects capabilities | Expected AirPack capabilities detected | PASS | 2026-07-08 log: `Detected 14 capabilities` |
| 6 | Entity count stable | Approx. 367–370 entities visible | PARTIAL | User-reported ~350–370 entities; screenshot/state export still pending |
| 7 | No duplicate unique/entity IDs | No HA unique-ID warning | PARTIAL PASS | No such warning observed in captured 2026-07-08 ThesslaGreen log; full HA entity screenshot pending |
| 8 | Basic write path | Writes complete without failure | PARTIAL PASS | `air_flow_rate_manual` 50.0 and 30.0 succeeded |
| 9 | Fan percentage operation | GUI updates correctly; no rollback | PENDING | Need fan card screenshots/log after 30 → 50 → 30 and/or other percentages |
| 10 | Targeted read-back allow-list | Safe number/select/switch read-back works; excluded registers use refresh | PENDING | Need DEBUG log with `Targeted read-back for <register>` for an allow-listed entity and no read-back for excluded entity |
| 11 | Full refresh after fan writes | Fan path keeps `targeted_readback=False`; one trailing refresh | PARTIAL | No targeted read-back lines observed; need full fan operation DEBUG log/screenshot |
| 12 | `validate_known_registers` | Stable supported/missing result; no mismatch | PASS | 2026-06-09 service result, supported=338/missing=19 |
| 13 | `refresh_device_data` service | Service succeeds and coordinator updates | PENDING | Not yet captured |
| 14 | Diagnostics download | JSON downloads and redacts host/serial as expected | PENDING | Not yet captured |
| 15 | Clock entity visible | `device_clock` exists | User-reported | Screenshot/state still pending |
| 16 | Clock sync | Sync works if options enabled | PENDING / N/A | Options are disabled by default; test only if enabled intentionally |
| 17 | No `transaction_id mismatch` | No mismatch during scan/write/poll | PASS for captured log | 2026-07-08 log negative search |
| 18 | No false transport disconnected | No false disconnected errors | PASS for captured log | 2026-07-08 log negative search |
| 19 | No ThesslaGreen ERROR entries | No integration ERROR lines | PASS for captured log | 2026-07-08 log negative search |
| 20 | Longer polling stability | Several normal 30 s refresh cycles without errors | PENDING | Need longer log after 30–60 minutes or overnight |

---

## 6. Targeted read-back allow-list validation

The targeted read-back policy is now an explicit allow-list in `coordinator/schedule.py`. Only single-word holding registers known to be 1:1 with a displayed number/select/switch state are eligible.

Excluded groups include:

- `uart_*` communication config
- `lock_*`, `access_level`
- `configuration_mode`, `cfg_mode_*`
- `language`, `rtc_cal`, `device_name`, `date_time*`
- reset/trigger/self-clearing registers
- `schedule_*` BCD-time registers
- `setting_*` AATT schedule-setting registers
- coils and multi-word registers
- fan writes through the fan entity, because fan display is based on status registers
- climate and service write paths, which intentionally pass `targeted_readback=False`

### 6.1 Required live tests

| # | Test | Expected result | Current status |
|---|------|-----------------|----------------|
| 1 | Change allow-listed number entity, e.g. `number.comfort_temperature` | DEBUG log shows targeted read-back and UI converges quickly | PENDING |
| 2 | Change allow-listed select entity, e.g. `select.mode` | DEBUG log shows targeted read-back and current option updates | PENDING |
| 3 | Change allow-listed switch entity, e.g. special mode / bypass/gwc lock if safe | DEBUG log shows targeted read-back and switch state updates | PENDING |
| 4 | Change fan percentage through fan entity | No targeted read-back for fan setpoint writes; one full refresh after operation | PARTIAL — latest log shows fan-related writes and no `Targeted read-back`; full UI evidence pending |
| 5 | Change non-allow-listed config entity only if safe and reversible | Write succeeds; no targeted read-back line; value converges by refresh | PENDING / optional |
| 6 | Confirm no mismatch after these writes | No `transaction_id mismatch` | PASS for 2026-07-08 captured writes; repeat after all tests |

---

## 7. Optimistic UI validation for controllable entities

Optimistic UI applies only to control/setpoint fields after a confirmed-successful write. It must never apply to measured/status/safety/identity fields.

### 7.1 Required live tests

| # | Test | Expected result | Current status |
|---|------|-----------------|----------------|
| 1 | Fan percentage 30 → 50 → 30 | GUI updates immediately; confirmed device state later matches; no rollback | PARTIAL — writes observed; GUI evidence pending |
| 2 | Number setpoint | GUI shows pending value immediately, confirmed later | PENDING |
| 3 | Switch | GUI flips immediately, confirmed later | PENDING |
| 4 | Select | GUI shows new option immediately, confirmed later | PENDING |
| 5 | Climate target temperature / hvac / fan / preset | Command fields can be optimistic; measured fields remain confirmed-only | PENDING |
| 6 | Measured/status fields | `current_temperature`, airflow, alarms, `device_clock`, diagnostics do not jump optimistically | PENDING |

---

## 8. Automated test coverage

The integration has comprehensive unit/CI coverage. Latest relevant checks before this docs-only update included:

| Test area | Status |
|-----------|--------|
| Python compileall | PASS |
| Ruff lint / import order / format | PASS |
| Pytest on Python 3.13 / HA test stack | PASS for latest runtime PRs |
| HACS validation | PASS |
| Hassfest validation | PASS |
| Entity mapping validation | PASS, 367 entities |
| Translation keys | PASS |
| AirPack4 vendor coverage | PASS, 0 missing |
| Targeted read-back allow-list tests | PASS in CI for #1745 |
| Connection helper consolidation tests | PASS in CI for #1748 |
| Read helper consolidation tests | PASS in CI for #1750 |

---

## 9. Real-device release gate

Real-device validation is **not complete** until:

1. Exact HA-installed integration commit SHA is recorded.
2. HA Core / OS versions for the latest validation log are recorded.
3. Entity count screenshot or state export is attached/committed.
4. Fan UI test is captured with logs and screenshot/video notes.
5. Targeted read-back allow-listed number/select/switch tests are captured at DEBUG level.
6. `refresh_device_data` and diagnostics download are tested.
7. Clock sync is tested if enabled; otherwise marked N/A with options disabled.
8. A longer polling log, preferably 30–60 minutes or overnight, shows no ThesslaGreen errors.
9. A named tester signs off with date and installed commit SHA.

Until then:

- `quality_scale` remains `bronze`.
- This document remains a partial evidence record, not full sign-off.

**Tester sign-off:** _(pending)_
**HA Core version tested for latest log:** _(pending)_
**Integration commit SHA tested for latest log:** _(pending)_
**Date tested:** 2026-07-08 log evidence recorded, formal sign-off pending
