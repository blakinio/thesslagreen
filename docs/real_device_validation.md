# Real-Device Validation Checklist

**Status: TEMPLATE — no real-device evidence yet.**

This document is a checklist and evidence template for real-device validation of the
ThesslaGreen Modbus integration. It must be filled with actual test results before
real-device validation can be claimed as complete for the 2.8.0 release.

---

## 1. Purpose

Verify that the integration functions correctly against a physical ThesslaGreen AirPack
controller over Modbus TCP. CI and unit tests cover code correctness; this checklist
covers end-to-end hardware behaviour.

---

## 2. Required Environment

| Component | Requirement |
|-----------|-------------|
| Home Assistant | ≥ 2026.1.0 (see `manifest.json → homeassistant`) |
| Integration version | 2.8.0 |
| Controller | ThesslaGreen AirPack or compatible (AirPack 4 confirmed in vendor docs) |
| Connection | Modbus TCP, reachable from HA host |
| Network | Stable LAN; controller IP and port accessible |
| Python | 3.13 (required by integration) |

---

## 3. Pre-Test Checklist

- [ ] Home Assistant installed and running (version recorded below).
- [ ] Integration installed from HACS custom repository or file copy.
- [ ] Controller powered on and reachable (ping or Modbus poll confirms).
- [ ] Controller firmware version noted.
- [ ] HA logs cleared before test run.
- [ ] No other Modbus client active on same controller during test.

---

## 4. Test Cases

### TC-01: Install via HACS custom repository
- [ ] Add custom repository `https://github.com/blakinio/thesslagreen` to HACS.
- [ ] Integration appears in HACS with name "ThesslaGreen Modbus" and correct version.
- [ ] Install completes without error.

### TC-02: Add integration via UI config flow
- [ ] Navigate to Settings → Integrations → Add Integration → ThesslaGreen Modbus.
- [ ] Enter controller IP and Modbus TCP port.
- [ ] Config flow completes; integration entry created.
- [ ] No error logged during setup.

### TC-03: TCP connection established
- [ ] HA log shows successful Modbus TCP connection to controller.
- [ ] No `ConnectionException` or `ModbusIOException` in logs within first 60 s.

### TC-04: Entity creation
- [ ] Entities appear in HA under the integration device.
- [ ] Entity count is approximately 366 (matching `validate_entity_mappings` output).
- [ ] No entity is in `unavailable` state due to mapping error.

### TC-05: Sensor updates
- [ ] Temperature, fan speed, and status sensor entities update on polling interval.
- [ ] Values are plausible (e.g., temperature within expected range).

### TC-06: Fan/climate controls
- [ ] Fan speed setpoint can be changed via entity in HA UI.
- [ ] Controller responds; polling reflects new value within one poll cycle.
- [ ] Climate mode or bypass setpoint writable if applicable.

### TC-07: Single register write path
- [ ] At least one writable register (e.g., fan speed) is changed via HA service call.
- [ ] Modbus write issued; read-back confirms new value.
- [ ] No exception in HA log.

### TC-08: Multi-register write path (if applicable)
- [ ] If any entity writes multiple registers atomically, trigger that write.
- [ ] All registers updated; read-back confirms.

### TC-09: Reconnect after controller restart
- [ ] Controller is power-cycled or Modbus TCP connection dropped.
- [ ] HA logs show connection lost, then reconnect within polling interval.
- [ ] Entities return to normal state after reconnect; no manual HA restart required.

### TC-10: Reconnect after network interruption
- [ ] Network path to controller is disrupted (cable, switch port, or firewall rule).
- [ ] HA logs connection error without crash.
- [ ] Connection restored after network restored; entities recover.

### TC-11: Unload and reload
- [ ] Integration unloaded via Settings → Integrations → ThesslaGreen Modbus → Delete
  (or via `hass.config_entries.async_unload`).
- [ ] Entities removed cleanly; no lingering tasks in log.
- [ ] Re-added immediately; setup completes without stale-state errors.

### TC-12: Home Assistant restart recovery
- [ ] HA restarted while integration is configured.
- [ ] Integration re-initialises cleanly on startup.
- [ ] Entities available and polling resumes within 60 s.

### TC-13: Log review
- [ ] After 10 min steady-state polling, HA log reviewed.
- [ ] No repeated exceptions, no flood of warnings.
- [ ] Poll interval consistent with configured value.

---

## 5. Evidence Record

Fill one copy of this section per test run.

```
Date:
Tester:
HA version:
Integration version: 2.8.0
Controller model:
Controller firmware:
Modbus TCP host/port:
Python version:

TC-01 Install via HACS:         PASS / FAIL / SKIP
TC-02 Config flow:              PASS / FAIL / SKIP
TC-03 TCP connection:           PASS / FAIL / SKIP
TC-04 Entity creation:          PASS / FAIL / SKIP
  Entity count observed:
TC-05 Sensor updates:           PASS / FAIL / SKIP
TC-06 Fan/climate controls:     PASS / FAIL / SKIP
TC-07 Single register write:    PASS / FAIL / SKIP
TC-08 Multi-register write:     PASS / FAIL / SKIP / N/A
TC-09 Reconnect after restart:  PASS / FAIL / SKIP
TC-10 Reconnect after network:  PASS / FAIL / SKIP
TC-11 Unload/reload:            PASS / FAIL / SKIP
TC-12 HA restart recovery:      PASS / FAIL / SKIP
TC-13 Log review:               PASS / FAIL / SKIP

Overall result: PASS / FAIL

Notes / log excerpts:
```

---

## 6. Completion Criteria

Real-device validation is **not complete** until:

1. All TC-01 through TC-13 entries are filled with actual results (not SKIP, unless
   the test case is genuinely not applicable to the hardware in use).
2. Overall result is PASS.
3. Evidence record is committed to this file or attached to the release PR.

**Do not mark real-device validation as complete without a filled evidence record.**

---

## 7. Known Gaps (as of 2026-05-09)

- No hardware test has been performed for the 2.8.0 release as of this document's
  creation. This remains release blocker B4.
- CI and unit tests (1948 passed, 4 skipped) provide code-level confidence but do not
  substitute for hardware validation.
