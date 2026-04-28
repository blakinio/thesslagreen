# Home Assistant Quality Scale

## Current target
Silver

## Silver checklist
- config entry unload closes transport
- entities become unavailable when device is offline
- offline logged once
- recovery logged once
- service actions raise HomeAssistantError / ServiceValidationError
- parallel updates configured intentionally
- config flow tests
- unload/reload tests
- runtime_data used for coordinator
- no platform stubs

## Gold checklist
- diagnostics without secrets
- repair issues for actionable problems
- reconfigure flow
- discovery DHCP/zeroconf if reliable
- entity_category for diagnostic/config entities
- disabled_by_default for noisy entities
- entity/exception/icon translations
- supported devices docs
- supported functions docs
- troubleshooting docs
- full platform tests with real HA
