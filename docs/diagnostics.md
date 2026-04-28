# Diagnostics

## Where to download diagnostics
From Home Assistant UI for this integration/config entry.
TODO: verify exact HA menu path wording.

## What diagnostics include
- Integration configuration snapshot (redacted).
- Runtime status and connectivity context.
- Poll/update statistics.
- Scan-related state/caches.

## What is redacted
Diagnostics must not expose passwords, tokens, precise private data, or sensitive network secrets.

## Runtime status
Includes online/offline and recent update behavior.
TODO: verify exact status fields from code.

## Connection statistics
Includes timing/error counters useful for troubleshooting.
TODO: verify exact counters from code.

## Scan cache
May include detected capabilities and register availability cache.
TODO: verify exact cache keys from code.

## Failed/skipped registers
May include unsupported/failed ranges for diagnostics context.
TODO: verify exact representation from code.

## Log level service
Temporary debug log level can be controlled via service.
See `docs/services.md`.
