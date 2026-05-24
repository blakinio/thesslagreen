# AirPack4 Deferred Registers

This document lists registers from the AirPack4 vendor reference (`airpack4_modbus.json`)
that are intentionally deferred — i.e., not yet added to the integration register map
(`thessla_green_registers_full.json`).

## Policy

A register is "deferred" when:
- Its semantics are not yet fully understood from the vendor documentation
- Adding it requires a firmware-version guard that is not yet implemented
- It is documented as device-variant-specific and the variant is not yet supported

Deferred registers are tracked here so they are not silently lost during coverage audits.
The automated test `test_airpack4_vendor_reference_coverage.py::test_no_unclassified_missing_registers`
fails if any vendor register is absent from the integration AND absent from the `DEFERRED`
set in that test file.

## Currently deferred registers

**None.**

As of the addition of E197 (FC03 0x20C7, PR refactor/airpack4-reference-coverage),
all 353 registers from the vendor reference are present in the integration register map.

## Previously deferred (now resolved)

| Register | Vendor name | FC | Address | Resolution |
|----------|-------------|-----|---------|------------|
| E197 | `E197` | FC03 | 0x20C7 (8391) | Added as `e_197` — auto-reset alarm flag |

## How to add a deferred register

1. Add the `(fc_num, address_dec)` tuple to the `DEFERRED` set in
   `tests/test_airpack4_vendor_reference_coverage.py::test_no_unclassified_missing_registers`.
2. Add a row to the "Currently deferred" table above with justification.
3. Open a follow-up issue or PR to resolve the deferral.
