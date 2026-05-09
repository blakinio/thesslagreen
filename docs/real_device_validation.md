# Real-Device Validation Checklist

> **Status: TEMPLATE ONLY — not yet filled with real evidence.**
>
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

### 4.11 Log Review

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 11.1 | Review full HA log after all above tests | No unhandled exceptions from `thessla_green_modbus`; no `ERROR` level messages during steady-state | | |
| 11.2 | No memory growth / resource leak visible after extended operation (optional) | Memory stable over 1-hour run | | |

---

## 5. Evidence Record

Fill this section after completing the tests above. **Do not claim validation
complete unless all mandatory test cases (4.1–4.11) are marked Pass.**

| Field | Value |
|-------|-------|
| **Date** | _YYYY-MM-DD_ |
| **Tester** | _Name / GitHub handle_ |
| **Home Assistant version** | _e.g., 2026.2.3_ |
| **Integration version** | _e.g., 2.8.0_ |
| **Controller model** | _e.g., ThesslaGreen AirPack 4_ |
| **Controller firmware** | _e.g., 3.14_ |
| **Modbus TCP port** | _e.g., 502_ |
| **Python version on HA host** | _e.g., 3.13.2_ |
| **Overall result** | _PASS / FAIL / PARTIAL_ |
| **Failed test cases** | _List IDs or "none"_ |
| **Notable log excerpts** | _Paste key log lines or "none"_ |
| **Additional notes** | |

---

## 6. Release Gate

Real-device validation is **not** complete until:

1. All test cases 4.1 through 4.11 are marked **Pass** in the Evidence Record above.
2. The Evidence Record is signed by a named tester.
3. This document is committed to the repository with the completed evidence.

Until that point, this document is a **template only** and real-device
validation remains an open release blocker (B4).
