# Runtime flow — thessla_green_modbus

How the integration comes up, polls, serves writes, and tears down at runtime.
Companion to `file_inventory.md` (what each file owns) and `write_path.md` (how a
write reaches Modbus). Descriptions are intentionally short.

Layering and ownership:

```text
HA platforms  ──►  coordinator/  ──►  core/DeviceClient  ──►  registers/ + scanner/  ──►  transport/  ──►  pymodbus
   (entities)      (HA adapter)       (sole I/O owner)          (defs / discovery)          (Modbus)
```

`DeviceClient` is the **single owner** of the Modbus connection and all I/O. The
coordinator is a Home-Assistant adapter and never talks Modbus directly.

## End-to-end lifecycle

```text
Config flow (user)                         Runtime (per config entry)
──────────────────                         ──────────────────────────
user/network form                          async_setup_entry (__init__.py)
      │                                            │
      ▼                                            ▼
device scan (scanner/, own connection)     async_create_coordinator ── builds CoordinatorConfig
      │  available_registers, caps, model         │                     + DeviceClient (owns IO)
      ▼                                            ▼
prepare_entry_payload  ── caches scan       async_start_coordinator
into entry.options["config_flow_scan_cache"]      │   ├─ coordinator.async_setup()  (scan or reuse cache)
      │                                            │   └─ async_config_entry_first_refresh()
      ▼                                            ▼
config entry created                        entry.runtime_data = coordinator
                                                   │
                                                   ├─ async_setup_mappings (options + entity maps)
                                                   ├─ async_migrate_entity_unique_ids
                                                   ├─ async_setup_platforms (forward to entity platforms)
                                                   ├─ ClockSyncManager.attach()
                                                   └─ async_setup_services (first entry only)
                                                          │
                                          ┌────────────────┴───────── every scan_interval ──────────┐
                                          ▼                                                          │
                                   _async_update_data ──► DeviceClient._read_all_register_data ──► transport
                                          │                                                          │
                                          ▼                                                          │
                                   entities read coordinator.data ◄──────────────────────────────────┘

unload/reload: async_unload_entry ─► unload platforms ─► coordinator.async_shutdown() ─► disconnect
options changed: async_update_options ─► full config-entry reload
```

## 1. Config-flow scan

- `_config_flow/` drives the user/network forms and validation, then runs a device
  **scan** through `scanner/` to discover `available_registers`, capabilities, model
  and firmware. The scan opens its own Modbus connection for the probe.
- Real-device safety: scanning uses the safe/normal path; unsupported registers
  (Modbus exception code 2) are treated as *not present*, not fatal. Unknown
  registers are **never** turned into entities automatically.
- `prepare_entry_payload` (`_config_flow/entry.py`) builds the entry `data` +
  `options`, and stores a **one-time** `config_flow_scan_cache` in `options` so the
  first runtime setup can skip a redundant scan.

## 2. DeviceClient ownership

- The coordinator constructor (`coordinator/coordinator.py`) creates the
  `ThesslaGreenDeviceClient` **first** and holds it as `self._device_client`
  (exposed read-only via `coordinator.device_client`).
- `DeviceClient` owns: the transport, connection lifecycle, `_client_lock` /
  `_write_lock`, retry/backoff, register reads/writes, and capability scanning.
- The coordinator exposes thin boundary adapters (`_ensure_connection`,
  `_disconnect`, `_test_connection`) that delegate into `DeviceClient`. These are
  intentional boundaries, **not** proxy debt — do not remove them.

## 3. Coordinator setup

- `async_create_coordinator` normalises config (connection type/mode, batch, backoff)
  and instantiates the coordinator.
- `async_start_coordinator` runs `coordinator.async_setup()` (which either applies
  the config-flow scan cache, loads the forced full register list, or runs a device
  scan via `scanner/`) and then `async_config_entry_first_refresh()`.
- Connection/auth failures are converted to `ConfigEntryNotReady` (retry later) or a
  reauth flow; they do not crash setup.

## 4. Entity setup

- `async_setup_mappings` loads option lists + entity mappings (`mappings/`,
  `options/`).
- `async_migrate_entity_unique_ids` upgrades legacy unique IDs **in place** via
  `unique_id_migration.py` so existing entities keep their identity.
- `async_setup_platforms` forwards setup to each platform in `const.PLATFORMS`.
  Entities subclass `ThesslaGreenEntity`; they only create entities for
  **available** registers and read their state from `coordinator.data`.
- `unique_id` and `suggested_object_id` (register-key based) are stable public
  contracts and must not change format.

## 5. Polling / update path

- `DataUpdateCoordinator` calls `_async_update_data` every `scan_interval`.
- `run_update_cycle` (`coordinator/update.py`): `_ensure_connection` → verify
  transport connected → `DeviceClient._read_all_register_data()` (batched reads via
  `core/` + `registers/read_planner`) → `apply_success_result` publishes a fresh
  `coordinator.data` dict and updates stats.
- An in-progress guard (`begin_update_cycle`/`finish_update_cycle`) and the shutdown
  flag prevent overlapping/stale cycles. Failures go through `handle_update_error`,
  which manages offline/unavailable state and logs recovery.
- Entities re-render on the coordinator's listener notification.

## 6. Service registration

- Services are registered once, when the **first** config entry is set up
  (`async_setup_services`), and removed when the **last** entry is unloaded.
- Handlers live in `services/` grouped by concern (mode, schedule, parameters,
  maintenance, data, logging). Service and field IDs match `services.yaml` and the
  translation keys — all are public contracts.
- Service register writes go through the shared dispatch with
  `refresh=False, targeted_readback=False`, and each handler issues its own refresh
  (see `write_path.md`).

## 7. Unload / reload lifecycle

- `async_unload_entry`: unload platforms → if successful, `coordinator.async_shutdown()`
  (stops listeners, disconnects transport) → unload services when it was the last
  entry.
- `async_update_options` performs a **full config-entry reload** rather than
  live-patching, because most options affect entity creation and register
  availability; a reload guarantees a clean, consistent state.
- `async_migrate_entry` handles config-entry schema version migrations.

## 8. Real-device validation expectations

- `quality_scale` stays `bronze` until `docs/real_device_validation.md` is marked
  PASS with committed real-device evidence — do not raise it speculatively.
- For validation on hardware use `validate_known_registers` (reuses the active
  connection). Avoid `scan_all_registers` as routine validation: it opens a
  **separate** Modbus connection and only one Modbus tool should talk to the device
  at a time.
- Modbus exception code 2 = unsupported register/range, not a device failure.
- Do not add unknown registers as entities, and do not change register
  addresses/names or entity/service IDs based on scan output.
