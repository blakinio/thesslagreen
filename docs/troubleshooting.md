# Troubleshooting

## Symptom: Cannot connect to device
### Description
Integration cannot establish Modbus communication.

### Resolution
- Verify IP/port or serial settings.
- Verify Modbus is enabled on device.
- Confirm no other controller keeps exclusive connection.
- Check Home Assistant logs and diagnostics dump.

## Symptom: Entities are unavailable
### Description
Entities exist but current state is unavailable.

### Resolution
- Confirm device is powered and reachable.
- Check communication timeouts in logs.
- Trigger manual refresh service.
- Reduce polling aggressiveness if link is unstable.

## Symptom: Some entities are missing
### Description
Only subset of expected entities is created.

### Resolution
- Missing entities may be unsupported on given model/firmware.
- Run register scan if available.
- Review diagnostics for skipped/unsupported registers.

## Symptom: Timeout / slow polling
### Description
Updates are delayed or frequent timeouts occur.

### Resolution
- Check network/serial quality.
- Increase scan interval.
- Ensure only one active Modbus client is polling device.

## Symptom: Illegal data address / unsupported register
### Description
Device rejects selected register address/range.

### Resolution
- Treat as unsupported register on current firmware/model.
- Avoid forcing unsupported writes/reads.
- Re-scan capabilities and review diagnostics.

## Symptom: Another Modbus client is connected
### Description
Parallel external client competes for device communication.

### Resolution
- Stop other client or reduce to one active polling owner.
- Re-test stability after exclusive access is restored.
