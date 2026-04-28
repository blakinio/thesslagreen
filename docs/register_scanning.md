# Register scanning

## Purpose
Detect device capabilities and available register/function set.

## Safe scan
Conservative probing focused on low-risk essential ranges.
TODO: verify from code.

## Normal scan
Default detection mode for typical capability discovery.
TODO: verify from code.

## Deep scan
Extended probing for additional optional capabilities.
TODO: verify from code.

## Full register list mode
Diagnostic mode that attempts broad probing against register definitions.
Full register list mode is diagnostic and may expose entities/registers that are not supported by a given device.

## Scan cache
Scan results may be cached to reduce repeated probing.
TODO: verify cache lifetime and storage from code.

## Known missing registers
Some registers may be absent on specific model/firmware combinations.

## Unsupported registers
Unsupported registers should be handled gracefully and not treated as fatal for whole integration.

## When to rescan
- After firmware/device change.
- After significant config/protocol changes.
- When expected entities are missing.

## Risks of full scan
- Longer scan time.
- Extra load on communication channel.
- More unsupported-address errors in logs.
