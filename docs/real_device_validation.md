# Real-Device Validation Checklist

> **Status: NOT YET COMPLETED**
>
> This document is a template. Real-device validation has not been performed.
> Do not mark real-device validation complete until this document contains
> a fully completed Evidence section signed by a tester with a real device.

---

## 1. Purpose

This document defines the minimum real-device validation required before a
ThesslaGreen Modbus Integration release is considered production-ready. It must
be completed by a human tester with access to a physical ThesslaGreen AirPack
(or compatible controller) and a running Home Assistant instance.

Automated tests (`pytest`) cover logic and mocked Modbus I/O. They cannot
substitute for on-device verification of the full communication path, entity
lifecycle, and UI behaviour.

---

## 2. Required Environment

| Item | Requirement |
|------|-------------|
| Home Assistant | ≥ 2026.1.0 (from `manifest.json → homeassistant`) |
| Integration version | 2.8.0 (tag `v2.8.0` or HACS custom-repository install) |
| Controller | ThesslaGreen AirPack 4 or compatible unit with Modbus TCP enabled |
| Modbus TCP | Controller reachable on the local network; IP and port known |
| Python on HA host | ≥ 3.13 (required by `pyproject.toml → requires-python`) |
| Network | Home Assistant host and AirPack on same subnet (or routed) |

---

## 3. Pre-Test Checklist

- [ ] Home Assistant is at target version and running.
- [ ] Integration is **not** yet installed (clean install path).
- [ ] Controller is powered on and Modbus TCP is accessible (test with
      `nc -z <controller-ip> <port>` from HA host).
- [ ] HA logs are clear (no unrelated errors from other integrations).
- [ ] A way to capture HA logs during the test is available
      (HA Settings → System → Logs, or `journalctl -u homeassistant`).

---

## 4. Test Cases

### 4.1 Installation

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 1.1 | Install integration via HACS (custom repository or HACS store once listed) | Integration appears in HACS, download completes without errors | | |
| 1.2 | Restart Home Assistant after installation | HA restarts cleanly; no import errors for `thessla_green_modbus` in logs | | |

### 4.2 Configuration Flow (UI)

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 2.1 | Add integration via HA Settings → Devices & Services → Add integration → ThesslaGreen Modbus | Config flow opens with host/port fields | | |
| 2.2 | Enter controller IP and port; submit | Integration is added without error | | |
| 2.3 | Verify no error dialog appears during setup | No `ModbusException` or `ConnectionException` shown | | |

### 4.3 TCP Connection

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 3.1 | Check HA logs immediately after setup | Log line confirming connection established; no repeated connection errors | | |
| 3.2 | Observe for 60 seconds | No repeated `ConnectionException` or timeout errors in logs | | |

### 4.4 Entity Creation

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 4.1 | Navigate to the integration device page | Entities visible in device list | | |
| 4.2 | Count entities (approximate) | ~366 entities created (matches `validate_entity_mappings.py` output) | | |
| 4.3 | Verify entity domains present | `sensor`, `binary_sensor`, `number`, `select`, `switch`, `fan`, `climate` domains all present | | |

### 4.5 Sensor / State Updates

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 5.1 | Wait one polling cycle (default 30 s) | Sensor states update from `unknown`/`unavailable` to real values | | |
| 5.2 | Verify supply air temperature sensor shows a plausible value | Temperature in expected range (e.g., 10–40 °C) | | |
| 5.3 | Verify fan speed sensor shows a plausible value | Fan speed in 0–100% range | | |

### 4.6 Fan / Climate Controls

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 6.1 | Change fan speed via HA UI (e.g., `number.fan_speed_supply`) | New value accepted; entity reflects new state within one poll cycle | | |
| 6.2 | Change climate setpoint via HA UI if climate entity present | New setpoint written; controller reflects change | | |

### 4.7 Register Write Paths

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 7.1 | Write to a single-register entity (e.g., fan speed number) | Register write succeeds; no `ModbusWriteException` in logs | | |
| 7.2 | Write to a multi-register entity if applicable | Write path completes; all target registers updated | | |

### 4.8 Reconnect After Disruption

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 8.1 | Disconnect controller from network for 30 s, then reconnect | Integration detects disconnection (entities unavailable) and reconnects automatically without HA restart | | |
| 8.2 | Restart controller (power cycle) while HA is running | Integration detects disconnection and reconnects automatically once controller is back | | |

### 4.9 Unload / Reload

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 9.1 | Disable integration via HA Settings → Devices & Services | Integration unloads; entities become unavailable; no errors in logs | | |
| 9.2 | Re-enable integration | Integration reloads; entities recover their states within one poll cycle | | |

### 4.10 Home Assistant Restart Recovery

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 10.1 | Restart Home Assistant | Integration re-initialises cleanly; no `ImportError` or `ConfigEntryNotReady` loop | | |
| 10.2 | Check logs after restart | No repeated error messages; connection established within ~30 s | | |

### 4.11 Options Flow Update

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 11.1 | Open integration options via HA Settings → Devices & Services → Configure | Options form opens with current values pre-filled | | |
| 11.2 | Change scan interval or another option; submit | Integration reloads with new settings; no errors in logs | | |

### 4.12 Special Modes (Boost / Eco / Away / Others)

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 12.1 | Call `thessla_green_modbus.set_special_mode` service with `mode: boost` | Boost mode activated on controller; register value changes to 1 | | |
| 12.2 | Call with `mode: eco` | Eco mode activated; register value changes to 2 | | |
| 12.3 | Call with `mode: away` | Away mode activated; register value changes to 3 | | |
| 12.4 | Call with `mode: none` (or deactivate) | Special mode deactivated; register resets to 0 | | |
| 12.5 | Verify climate entity preset_mode reflects the active special mode | Climate entity shows correct preset after one poll cycle | | |

### 4.13 Clock Sync

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 13.1 | Enable clock sync in options (`sync_device_clock_enabled: true`) | Integration writes current time to controller time registers on startup | | |
| 13.2 | Wait for the sync interval (or call `thessla_green_modbus.sync_device_clock`) | Clock registers on controller updated; log shows "Clock sync" message | | |
| 13.3 | Verify no `ModbusException` during clock write | No write error in logs | | |

### 4.14 Diagnostics

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 14.1 | Navigate to the integration device page → Download diagnostics | Diagnostics JSON downloads without error | | |
| 14.2 | Open diagnostics JSON | Contains `available_registers`, `statistics`, `device_info`, `scanned_registers` fields | | |
| 14.3 | Verify no sensitive data (credentials, tokens) in diagnostics output | Diagnostics file safe to share | | |

### 4.15 Service Calls

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 15.1 | Call `thessla_green_modbus.set_airflow_rate` with a valid value | Airflow rate register updated; entity reflects new value | | |
| 15.2 | Call `thessla_green_modbus.set_temperature_curve` if applicable | Temperature curve registers updated without error | | |
| 15.3 | Call `thessla_green_modbus.set_log_level` with `level: debug` | Log level changes; additional debug messages appear in HA log | | |

### 4.16 Log Review (No Traceback)

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 16.1 | Review full HA log after all above tests | No unhandled exceptions from `thessla_green_modbus`; no `ERROR` level messages during steady-state | | |
| 16.2 | No traceback (`Traceback (most recent call last)`) in log from integration code | Zero tracebacks during normal operation | | |
| 16.3 | No memory growth / resource leak visible after extended operation (optional) | Memory stable over 1-hour run | | |

---

## 5. Evidence Record

Fill this section after completing the tests above. **Do not claim validation
complete unless all mandatory test cases (4.1–4.16) are marked Pass.**

| Field | Value |
|-------|-------|
| **Date** | _YYYY-MM-DD_ |
| **Tester** | _Name / GitHub handle_ |
| **Home Assistant version** | _e.g., 2026.2.3_ |
| **Integration version / commit SHA** | _e.g., 2.8.0 / abc1234_ |
| **Controller model** | _e.g., ThesslaGreen AirPack 4_ |
| **Controller firmware** | _e.g., 3.14_ |
| **Connection type** | _TCP / RTU / TCP\_RTU_ |
| **Slave ID** | _e.g., 1_ |
| **Modbus host:port** | _e.g., 192.168.1.50:502_ |
| **Python version on HA host** | _e.g., 3.13.2_ |
| **Overall result** | _PASS / FAIL / PARTIAL_ |
| **Failed test cases** | _List IDs or "none"_ |
| **Debug log excerpt** | _Paste key log lines or "none"_ |
| **Known limitations** | _Any known issues observed during test_ |
| **Additional notes** | |

---

## 6. Real-Device Findings Cleanup (2026-05-09)

The following findings were identified from exported HA state data and addressed in
this PR (`fix: address real-device validation findings`).

| Finding | Status | Fix / Decision | Evidence |
|---|---|---|---|
| Fan percentage 109 (> 100) | FIXED | `fan.py` `percentage` property clamped to 100 per HA spec; raw value preserved in `supply_percentage` attribute | Unit test `test_fan_percentage_109_clamped_to_100`; `test_fan_percentage_limits.py` updated |
| `number.airing_coef` state 50 outside range 100–150 | NEEDS_VENDOR_CONFIRMATION | Write range unchanged (100–150) per declared metadata. Reading 50 does not crash. Vendor confirmation needed to determine if 50 is valid or a factory default. | Tests `test_airing_coef_native_value_below_min_does_not_crash`, `test_airing_switch_coef_native_value_zero_does_not_crash` |
| `binary_sensor.fire_alarm` raw true / state off | CONFIRMED_CORRECT | NC (normally-closed) contact: raw True = circuit closed = no alarm = `is_on=False`. Mapping has `inverted: True` with inline comment. | Tests `test_fire_alarm_raw_true_means_no_alarm`, `test_fire_alarm_inverted_flag_present` |
| `binary_sensor.dp_duct_filter_overflow` raw true / state on | CONFIRMED_CORRECT | Raw True = problem detected. `device_class=problem` is correct. This is a real hardware problem state. | Test `test_dp_duct_filter_overflow_raw_true_is_problem` |
| `sensor.serial_number` unavailable / device info Unknown | DEFERRED (partially improved) | `sw_version` now assembled from `version_major.version_minor CF<cf_version>` when firmware is Unknown (e.g. `3.11 CF13`). Serial decode root cause deferred — no crash occurs on bad bytes. | Tests `test_sw_version_uses_version_registers_when_firmware_unknown`, `test_get_device_info_uses_version_registers_for_sw_version` |
| `sensor.rekuperator_active_errors` state unknown | FIXED | `native_value` now returns `"none"` (not Python None) when coordinator has been successfully updated but no error codes are active. Before first update, returns None (correctly showing «unknown»). | Tests `test_active_errors_sensor_returns_none_string_when_no_errors` |
| `switch.bypass_off` / `switch.gwc_off` misleading names | FIXED | Translation-only fix: renamed from "Bypass Active" / "GWC Active" to "Bypass Locked" / "GWC Locked" (PL: "Bypass zablokowany" / "GWC zablokowany") to match register semantics (value 1 = deactivated). Entity IDs and unique IDs unchanged. | Translation tests pass; register JSON evidence: `enum: {0: aktywny, 1: nieaktywny (pasywny)}` |
| Polish state wording "nie działa" | CONFIRMED_CORRECT | Phrase appears only in S30/S31 error-code sensor *names* ("S30: Wentylator nawiewny nie działa"), which accurately describes the fault condition. No state labels use this phrase. | Test `test_nie_dziala_only_in_error_code_names` |

Schedule/entity-group hiding was **NOT** implemented in this PR.
Harmonogram entity cleanup was **NOT** implemented in this PR.

---

## 7. Release Gate

Real-device validation is **not** complete until:

1. All test cases 4.1 through 4.16 are marked **Pass** in the Evidence Record above.
2. The Evidence Record is signed by a named tester with the commit SHA recorded.
3. This document is committed to the repository with the completed evidence.

Until that point, this document is a **template only** and real-device
validation remains an open release blocker (B4).

Section 6 (real-device findings cleanup) is based on exported HA state data,
not a full on-device test run.  It does not satisfy the release gate above.
