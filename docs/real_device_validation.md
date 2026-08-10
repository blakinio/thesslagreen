# Real-Device Validation Report

**Status:** `PARTIAL`  
**Last historical physical evidence:** 2026-07-08  
**Post-hardening validation:** `PENDING`  
**Current code baseline requiring revalidation:** PR #1762 / `088677385a179a0a02c14ddae3dd96d20c2534e0` plus the 2026-08-10 follow-up when merged.

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

The follow-up task additionally removes the volatile process-memory energy accumulator and adds a Repairs issue lifecycle for final Modbus write failures.

Because these changes touch runtime behavior, old hardware evidence remains historical evidence only.

## 3. Required post-hardening validation matrix

Do not mark an item `PASS` without an exact log, service response, screenshot/state capture, or measured result.

| # | Check | Required evidence | Status |
|---|---|---|---|
| 1 | Exact build identity | integration commit/version visible in the test record | PENDING |
| 2 | Environment identity | HA Core/OS, AirPack model, firmware, transport, slave ID | PENDING |
| 3 | Fresh setup/reload | setup completes without ThesslaGreen traceback | PENDING |
| 4 | Normal polling | several consecutive refreshes with stable data | PENDING |
| 5 | Service registration | actions visible and callable after setup | PENDING |
| 6 | Fan write | representative 30 → 50 → 30 operation, state converges | PENDING |
| 7 | Climate write | representative safe setpoint/mode write | PENDING |
| 8 | Number/select/switch read-back | allow-listed write confirms through targeted read-back | PENDING |
| 9 | Write failure semantics | controlled unreachable/rejected write reports failure, not success | PENDING |
| 10 | Repairs lifecycle | final write failure creates issue; later successful write clears it | PENDING |
| 11 | `validate_known_registers` | stable supported/missing/indeterminate report | PENDING |
| 12 | Full diagnostic scan | isolated scan completes and normal connection is restored | PENDING |
| 13 | Network interruption | disconnect/reconnect recovers without manual reload | PENDING |
| 14 | Diagnostics download | file downloads and sensitive fields are redacted | PENDING |
| 15 | 30–60 minute stability | no mismatch/disconnect storm during normal polling | PENDING |
| 16 | 24–72 hour soak | no progressive transport or polling degradation | PENDING |
| 17 | RTU/USB | physical serial test with stable `/dev/serial/by-id/...` device path | PENDING |

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

## 6. Evidence template

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

## 7. Release interpretation

The integration may have green automated CI while this file remains `PARTIAL`; those are different evidence classes. A release description must state the actual hardware validation level and must not convert `PENDING` rows into claims based on unit tests.
