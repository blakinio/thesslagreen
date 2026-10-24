# AirPack Home 400h coverage and conformance review

## Scope and source identity

Base: `origin/main` at `d503923` (release 2.8.5), plus the four open
contributor fixes cherry-picked with authorship kept (transport `method`
keyword, service option lists, firmware-gated filter registers, shutdown
port release). The owner's unit is AirPack Home 400h.

Manufacturer contracts, from the owner's supplied PDFs (not committed or
republished):

- Home: internal revision `MODBUS_USER_AirPack_Home_06.2021.01`
  (supplied filename ends `08.2021.01.pdf`).
- AirPack4: `08.2022.01`.

An independent read-only review of the repository was run as a second opinion.
Each of its findings was reproduced locally before it was fixed. No
device or Home Assistant instance was contacted.

## Register coverage

| Check | Result |
| --- | --- |
| Home PDF register addresses (FC01-FC04) | 331 unique; all present in `registers/thessla_green_registers_full.json` (357) with matching access. |
| Repository registers absent from the Home table | AirPack4-only FC03 4482, 4483, 4660, 4662, 4704, 4711, 8220, 8300, 8332-8343, 8348, 8349, 8391, 8394, 8395 and FC04/23. Scanner availability gates them. |
| Home-only (absent from AirPack4) | FC03 8442, 8444 and FC04/298. All present. |
| E196-E199 | The Home table lists all four at 8390. This is kept as `e_196_e_199` at 8390, with `e_197` at 8391 for AirPack4. |
| filterChange 8191 | R/W on Home, R/- on AirPack4. Writes are profile-gated (see the 2026-10-21 audit). |

## Corrections in this change

| Area | Source and root cause | Fix |
| --- | --- | --- |
| Multi-word reads | Home p.13 `device_name` 8144-8151 (ASCII), FC04 24-29 serial, 8187/8188 product key ("save both registers"; 0x423f, 0x000f = 999999). Polling decoded each word on its own, so these values only ever held their first word. | `core/register_processing.assemble_multi_register_values` decodes from every word of the poll. An incomplete read is dropped. The `lock_pass` number range is now 0-999999. |
| Device name write | Short names were split into per-chunk encodes that wrote zeros over the following words. | The whole NUL-padded name is encoded once and the coordinator splits it into FC16 chunks. |
| Temporary mode | Home p.12: write 0x1130-0x1132 / 0x1133-0x1135 "in one operation". The number entities for 4401/4404 wrote one word. | They now use the coordinator's existing triplet writers. |
| RTC | FC03 0-3 date/time words could be split by a small batch size. | The clock sync and the `sync_time` service both require a single request. |
| HA lifecycle | The clock-sync listener was never removed. Reauth was awaited as a coroutine. | The listener is unsubscribed via `entry.async_on_unload`. Reauth is now called as a callback. |
| HA entity model | Percent airflow kept the volume-flow device class. | The device class is cleared when the unit is %. |
| Diagnostics privacy | Serial numbers were masked only at top level. | Serials are masked in nested sections, and raw FC04 24-29 words are redacted. |
| Unique IDs | A host-prefixed current-format ID was double-prefixed once the serial became known. | The current format is recognised under any prefix and the prefix is swapped. |
| Shutdown | The direct TCP client path bypassed the transport shutdown guard. | `call_modbus` refuses calls after shutdown. |
| Runtime requirements | The RTU transport needs pyserial. | `pyserial>=3.5` was added to the manifest and the project dependencies. |

## Verified unchanged

- Temperature sentinel 0x8000.
- BCD times and the 0xA200/0x2400 disabled markers.
- AATT encoding.
- 4224 special-mode enum, 4209 season and 4208 mode.
- 16-register request cap.
- Read-only write guards.

## Not verified

- No physical acceptance: these are protocol and contract fixes only.
- The multi-word assembly covers batch reads only. A chunk that falls back to
  single-register reads leaves the multi-word value unset for that poll.
