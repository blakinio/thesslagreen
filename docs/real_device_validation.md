# Real-Device Validation Report

**Status:** `BLOCKED`  
**Last historical physical evidence:** 2026-07-08  
**Post-hardening validation:** `FAILED` on 2026-08-16 for v2.8.4  
**Current code baseline requiring revalidation:** current `main`; every physical validation session must record the exact tested commit before execution.

This document is the source of truth for physical ThesslaGreen validation. Automated CI results must not be recorded as physical-device evidence.

## 1. What is already proven on a real unit

Historical evidence was collected from a user-reported ThesslaGreen AirPack 4 over Modbus TCP before the 2026-08-10 hardening work.

### 2026-07-08 Home Assistant log

The captured log proved, for the then-installed integration build:

- TCP setup completed;
- config-flow scan cache was reused;
- 14 capabilities were detected;
- integration setup and service registration completed;
- writes of `air_flow_rate_manual` to 50.0 and 30.0 succeeded;
- no `transaction_id mismatch` was observed in the captured interval;
- no false `Modbus transport is not connected` error was observed;
- no ThesslaGreen traceback was observed.

The exact integration commit installed in Home Assistant was **not** recorded, therefore this evidence cannot be promoted to post-#1762 validation.

### 2026-06-09 `validate_known_registers`

Observed on HA OS 17.3 / HA Core 2026.6.1:

- supported registers: 338;
- missing registers: 19;
- missing input registers: 4;
- missing holding registers: 15;
- individual fallback reads: 62;
- no transaction-ID mismatch observed during or immediately after the validation call.

The missing set included optional firmware metadata, hardware-gated post-heater registers, expansion/service registers, filter-date API fields, and internal UART configuration. Those definitions must not be deleted globally merely because they are absent on this tested unit.

## 2. What changed after that evidence

PR #1762 hardened behavior that directly affects hardware validation:

- service target resolution and global action lifecycle;
- write failure propagation to Home Assistant;
- fan/climate/text/time write semantics;
- targeted read-back behavior;
- full-scan transport isolation;
- safe classification of transport failures as `indeterminate` rather than unsupported;
- removal of redundant entity initial reads.

PR #1763 added the bounded hardening follow-up, including removal of the volatile process-memory energy accumulator and a Repairs issue lifecycle for final Modbus write failures. Subsequent `main` changes also remain outside the historical hardware evidence unless their exact candidate commit is explicitly tested and recorded below.

Because these changes touch runtime behavior, old hardware evidence remains historical evidence only.

## 3. Required post-hardening validation matrix

Do not mark an item `PASS` without an exact log, service response, screenshot/state capture, or measured result.

| # | Check | Required evidence | Status |
|---|---|---|---|
| 1 | Exact build identity | integration commit/version visible in the test record | PASS — v2.8.4 / `b198c626d20797978bb78dbbab1fe2934fc1dc32` |
| 2 | Environment identity | HA Core/OS, AirPack model, firmware, transport, slave ID | PARTIAL — all direct fields recorded except device model, which runtime reports as `Unknown` |
| 3 | Fresh setup/reload | setup completes without ThesslaGreen traceback | PASS — reload and later HA restart both recovered to `loaded`; one cancelled-read warning during reload |
| 4 | Normal polling | several consecutive refreshes with stable data | PASS — pre-advanced-test runtime showed 61 successful reads, 0 failed reads, 0 connection errors |
| 5 | Service registration | actions visible and callable after setup | PASS — 21 ThesslaGreen services registered |
| 6 | Fan write | representative 30 → 50 → 30 operation, state converges | PASS — 30% → 50% → 30%; physical flow 165/162 m³/h at 50%, then 99/97 m³/h after restore |
| 7 | Climate write | representative safe setpoint/mode write | **FAIL** — optimistic setpoint did not reliably match confirmed device value; mode round-trip also changed airflow/setpoint unexpectedly |
| 8 | Number/select/switch read-back | allow-listed write confirms through targeted read-back | PASS — number 31 → 30 confirmed; same-state select/switch writes logged decoded targeted read-back values |
| 9 | Write failure semantics | controlled unreachable/rejected write reports failure, not success | NOT RUN — withheld after release-blocking runtime failures were found |
| 10 | Repairs lifecycle | final write failure creates issue; later successful write clears it | NOT RUN — withheld with the controlled failure test for safety |
| 11 | `validate_known_registers` | stable supported/missing/indeterminate report | **FAIL** — service crashes with `_ClientBackedTransport.read_input_registers() missing 1 required positional argument: 'address'` |
| 12 | Full diagnostic scan | isolated scan completes and normal connection is restored | **FAIL** — `batch=4`, `delay=150ms` produced a sustained transaction-ID mismatch storm; scan was aborted by HA restart |
| 13 | Network interruption | disconnect/reconnect recovers without manual reload | NOT RUN — further deliberate disruption withheld after scan failure |
| 14 | Diagnostics download | file downloads and sensitive fields are redacted | PASS — diagnostics retrieved; host and serial fields were redacted |
| 15 | 30–60 minute stability | no mismatch/disconnect storm during normal polling | PASS for normal polling before advanced tests — at least ~40 minutes without failed reads/connection errors |
| 16 | 24–72 hour soak | no progressive transport or polling degradation | PENDING — requires a future uninterrupted soak on a fixed candidate |
| 17 | RTU/USB | physical serial test with stable `/dev/serial/by-id/...` device path | NOT RUN — this acceptance session used Modbus TCP |

## 4. Recommended test sequence

1. Install the exact candidate commit and record it before testing.
2. Restart Home Assistant and capture integration setup logs.
3. Leave normal polling running for several cycles before issuing writes.
4. Test one safe operation from each writable entity family actually supported by the device.
5. Verify targeted read-back only on allow-listed 1:1 registers.
6. Run `validate_known_registers` while normal integration ownership of Modbus is maintained.
7. Run the full diagnostic scan only as an explicit advanced test and verify the primary transport reconnects afterwards.
8. Simulate a network loss long enough to force retry/reconnect behavior.
9. Trigger one controlled final write failure, confirm the Repair issue appears, restore connectivity, perform a successful write, and confirm the issue clears.
10. Run the long soak without additional Modbus tools connected to the same controller.

## 5. RTU/USB rule

Prefer a persistent Linux device path such as:

```text
/dev/serial/by-id/usb-...
```

Do not use `/dev/ttyUSB0` as the canonical production example because enumeration can change after host or USB restarts.

Record actual baud rate, parity, stop bits, slave ID, adapter model, and path used in the evidence block.

## 6. Physical validation evidence

### 2026-08-16 — candidate `b198c626d20797978bb78dbbab1fe2934fc1dc32` / v2.8.4

- HA Core: 2026.8.2
- HA OS / install type: Home Assistant OS 18.1, x86_64 VM, Supervisor 2026.07.5
- Integration commit/version: HACS installed `v2.8.4`; manifest `2.8.4`; Git tag `v2.8.4` resolves to `b198c626d20797978bb78dbbab1fe2934fc1dc32`
- AirPack model: `Unknown` in direct runtime diagnostics; historical user-reported AirPack 4 is not promoted to direct v2.8.4 evidence
- Firmware: 3.11
- Register map: AirPack Home/Compact series 4 — Modbus register map rev. 2023-10
- Transport: TCP
- Endpoint: private LAN endpoint redacted from public evidence, TCP port 8899
- Slave ID: 10
- Poll interval: 30 s
- Configured batch size: 16
- Advanced scan test: batch 4, 150 ms delay

Results:

- **Build identity — PASS.** HACS reported installed `v2.8.4`, the integration manifest reported `2.8.4`, and repository tag `v2.8.4` resolves to the exact release SHA above.
- **Fresh reload/setup — PASS with warning.** A config-entry reload temporarily made entities unavailable while setup ran, then recovered without manual repair. One unload/setup warning recorded `Request cancelled outside library`; no ThesslaGreen traceback followed. A later full HA restart completed setup successfully again.
- **Normal polling — PASS before advanced tests.** Runtime diagnostics recorded 61 successful reads, 0 failed reads, 0 connection errors and 0 timeout errors before the disruptive validation steps.
- **Service registration — PASS.** Home Assistant exposed 21 `thessla_green_modbus` actions after setup.
- **Fan 30 → 50 → 30 — PASS.** Initial manual setpoint was 30%. At 50%, the direct device-derived supply/exhaust flow sensors rose to 165/162 m³/h and register-backed manual airflow reported 50. After restoring 30% and forcing a refresh, airflow returned to approximately 99/97 m³/h and the register-backed value returned to 30.
- **Simple number targeted read-back — PASS.** `number.thesslagreen_air_flow_rate_manual` was changed 30 → 31 → 30; Home Assistant returned verified states and raw register values 31 then 30.
- **Select/switch targeted read-back — PASS.** With temporary debug logging, a same-state write of `select.thesslagreen_mode=manual` logged `Targeted read-back for mode decoded to 1`; a same-state `switch.thesslagreen_comfort_mode_panel=off` logged `Targeted read-back for comfort_mode_panel decoded to 0`.
- **Climate setpoint — FAIL.** `climate.set_temperature(22.5)` returned success/optimistic 22.5, but a direct refresh confirmed 22.0 again. A second 23.0 test again exposed optimistic UI state while the independent `sensor.thesslagreen_required_temperature` remained at the physical value 22.0. The original 22.0 value was restored after testing.
- **Climate mode round-trip — FAIL.** Starting from `fan_only`, 30% and 22.0 °C, `fan_only → auto → fan_only` returned service success but after refresh the physical fan output fell to 10% while the manual airflow setpoint entity still held 30, and `required_temperature` became 0.0. Explicit fan/setpoint writes restored 30% / 22.0 °C and ~99/97 m³/h.
- **`validate_known_registers` — FAIL.** Invocation with batch 4 and 150 ms delay started, then failed in `services/handlers_data.py` with `TypeError: _ClientBackedTransport.read_input_registers() missing 1 required positional argument: 'address'`; no supported/missing/indeterminate report was produced.
- **Full diagnostic scan — FAIL and aborted.** `scan_all_registers` was started in isolated mode with batch 4, 150 ms delay and `known_registers_only=false`. The live log developed a sustained `request ask for transaction_id=37 but got id=..., Skipping` storm; more than 1,600 matching lines were observed while the scan was active. Home Assistant was restarted to terminate the scan. During shutdown the scan service task was still running and Home Assistant logged that it could not be cancelled cleanly during final shutdown.
- **Post-abort recovery — PASS after HA restart, not a PASS for the scan itself.** Recorder started a new run at 10:05:58 local time; the last observed transaction-ID mismatch was 10:04:49. ThesslaGreen setup completed successfully at 10:07:10, the integration returned to `loaded`, TCP diagnostics reported `connected=true`, and the physical baseline was confirmed as fan 30%, target 22.0 °C, supply/exhaust flow approximately 99/97 m³/h.
- **Diagnostics/redaction — PASS.** Integration diagnostics were downloadable through Home Assistant; the host appeared redacted as `192.xxx.xxx.12` and serial as `Un***wn` in the diagnostic payload.
- **30–60 minute normal-polling stability — PASS for the pre-advanced-test period only.** The integration had run for more than 40 minutes with no failed reads or connection errors before the deliberate validation/scan tests. The later scan storm is recorded separately as a diagnostic-scan failure and must not be conflated with normal polling.
- **Controlled write failure / Repairs / external network interruption — NOT RUN.** These disruptive checks were intentionally withheld after three release-blocking failures had already been directly demonstrated.
- **24–72 hour soak — PENDING.** A meaningful soak should be performed only on a candidate that fixes the failures above.
- **RTU/USB — NOT RUN.** This physical session tested TCP only.

### Evidence interpretation

The v2.8.4 physical acceptance gate is **not satisfied**. The three release-blocking findings are:

1. Climate writes can report/retain optimistic success without confirmed device convergence, and the tested HVAC mode round-trip caused unexpected physical setpoint/output changes.
2. `validate_known_registers` crashes before producing its validation report.
3. The isolated full diagnostic scan triggers a severe transaction-ID mismatch storm even at batch 4 with 150 ms pacing and does not terminate promptly during HA shutdown.

Do not merge the acceptance closeout or promote these rows to PASS until the runtime defects are fixed on a new candidate and the failed/withheld matrix items are re-run.

## 7. Evidence template

Append a dated section for every new physical validation session:

```markdown
### YYYY-MM-DD — candidate <commit>

- HA Core: ...
- HA OS / install type: ...
- Integration commit/version: ...
- AirPack model: ...
- Firmware: ...
- Transport: TCP / RTU-over-TCP / RTU
- Endpoint or serial adapter: ...
- Slave ID: ...
- Poll interval: ...
- Batch size: ...

Results:
- setup: PASS/FAIL + evidence
- polling: PASS/FAIL + evidence
- writes/read-back: PASS/FAIL + evidence
- reconnect: PASS/FAIL + evidence
- validate_known_registers: PASS/FAIL + counts
- full scan: PASS/FAIL + restoration evidence
- Repairs lifecycle: PASS/FAIL + evidence
- soak duration: ...
- errors/warnings: ...
```

## 8. Release interpretation

The integration may have green automated CI while this file remains `PARTIAL` or `BLOCKED`; those are different evidence classes. A release description must state the actual hardware validation level and must not convert `PENDING`, `NOT RUN`, `PARTIAL`, or `FAIL` rows into claims based on unit tests.
