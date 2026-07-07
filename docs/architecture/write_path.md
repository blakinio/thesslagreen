# Write path & targeted read-back — thessla_green_modbus

How a value entered in Home Assistant reaches a Modbus register, how the confirmed
state comes back, and which entities are allowed to show an optimistic value.
Grounded in `coordinator/schedule.py`, `coordinator/write_path.py`, `fan.py`,
`climate.py`, `services/`, and `docs/audits/targeted_readback_write_path_audit.md`.

> **Do not change** register addresses/names, entity/unique/service IDs, or
> translation keys. Do not broaden the write path reactively. The read-back policy
> is a deliberate, test-backed design — read the audit before touching it.

## 1. HA entity → Modbus write

```text
entity.async_set_*()                         (fan/climate/number/switch/select/...)
      │  value in user units
      ▼
ThesslaGreenEntity._write_register  ──►  coordinator.async_write_register(name, value,
      │                                        refresh=?, targeted_readback=?)
      ▼
coordinator/schedule.py: async_write_register
      │  async with DeviceClient._write_lock:              # serialises all Modbus IO
      │     _locked_single_register_write
      │        ├─ _resolve_write_definition(name)          # registers/ definition
      │        ├─ encode_write_value(...)                  # core/write_path.py: user units → raw
      │        └─ run_single_write_attempts (write_path.py)# retry/backoff loop
      │            └─ transport write_register / write_registers
      ▼
finalize_write_result ──► optional full refresh
```

Key points:

- `ThesslaGreenEntity._write_register` (`entity.py`) is the single simple-entity
  entry; it forwards `refresh` and lets the coordinator own read-back policy. It
  raises `RuntimeError` if the write returns `False`.
- All writes run under `DeviceClient._write_lock`, so no scan/poll/other write can
  interleave on the shared client (prevents pymodbus transaction-ID mismatches).
- Values are supplied in user-friendly units; `encode_write_value` converts to the
  raw Modbus representation using the register definition.

## 2. Targeted read-back rules

After a **successful** single-register write, still holding the write lock,
`async_write_register` may read the register straight back and publish the decoded
value — avoiding a full poll:

```python
if targeted_readback and definition is not None and _targeted_readback_safe(name, definition):
    raw = await self._locked_read_holding_registers(definition.address + offset,
                                                    count=definition.length)
```

`_targeted_readback_safe(name, definition)` is eligible **iff**:

- `name` is **not** in `_NO_READBACK_REGISTERS`
  (`hard_reset_settings`, `hard_reset_schedule`, `filter_change`,
  `airflow_rate_change_flag`, `temperature_change_flag`, `cfg_mode_1`, `cfg_mode_2`,
  `pres_check_day_2`, `pres_check_time_2`), **and**
- `definition.function == 3` (holding register — coils are excluded), **and**
- `definition.length == 1` (single word — multi-word blocks excluded), **and**
- `name` does **not** start with `schedule_` or `setting_` (BCD/AATT schedule slots).

Outcomes:

- **Read-back succeeds** → `refresh_after_write = False`; the **decoded device
  value** (not the requested value) is written into a copy of `coordinator.data` and
  published via `async_set_updated_data`. No full refresh. For enum registers the raw
  int is stored (to match the polling pipeline).
- **Read fails** (`_locked_read_holding_registers` returns `None`) → falls back to a
  full refresh iff `refresh=True`.
- **Decode fails after a good read** → caught; `coordinator.data` is left unchanged;
  full refresh armed iff `refresh=True`.

> **Invariant:** a read-back read/decode failure must **never** turn a successful
> write into a failure. The read is exception-swallowed to `None`; decode/publish
> happen **outside** the lock, each try/except-wrapped. Preserve this.

> **Note:** `refresh=False` does **not** disable read-back — only
> `targeted_readback=False` does. `refresh` only governs the full-refresh fallback.

The current policy is a **deny-list over a permissive default**: any writable
single-word holding register is eligible unless listed. This is a known, documented
latent breadth (dangerous config entities like `uart_*`, `lock_*`, `access_level`,
`configuration_mode` are eligible via their number/select entities). Narrowing it to
an allow-list is a planned follow-up (see the audit, "Stage 2") — **not** an
emergency, and out of scope for docs.

## 3. Full-refresh fallback

- When read-back is disabled or ineligible, `refresh_after_write` follows the
  caller's `refresh` flag; `finalize_write_result` then calls a debounced
  `async_request_refresh()`.
- When read-back is eligible but the read/decode fails, the coordinator re-arms a
  full refresh (if `refresh=True`) so the entity still converges to real device
  state on the next cycle.
- Multi-register writes (`async_write_registers`, temporary temp/airflow blocks,
  clock sync, device name) have **no** read-back path — they always use the full
  refresh flag.

## 4. Why fan/climate disable targeted read-back in some paths

- **Fan:** the displayed percentage comes from **status** registers
  (`supply_percentage` / `exhaust_percentage`), while the fan **writes** setpoint
  registers (`air_flow_rate_manual`, `mode`, `on_off_panel_mode`). A read-back of a
  setpoint would neither update the display nor be meaningful, so `fan._write_register`
  passes `targeted_readback=False`. A manual-mode percentage change writes `mode`
  then `air_flow_rate_manual` **both** with `refresh=False`, then issues a **single**
  trailing `async_request_refresh()` — no refresh sandwiched between the two writes.
- **Climate:** every write path (`hvac_mode`, `temperature`, `fan_mode`,
  `preset_mode`, `turn_on/off`) writes with `refresh=False, targeted_readback=False`
  and issues exactly one refresh at the end, because operations touch several
  registers whose relationship to displayed state is not 1:1.
- **Services:** all service register writes pass `targeted_readback=False` (shared
  dispatch). They target reset/trigger registers (self-clear to 0), comms params
  (`uart_*` — a read on a just-reconfigured link is untrustworthy), and multi-word
  blocks (clock, device name) where a single-word read-back is misleading.

The simple-entity platforms (`number`, `switch`, `select`, `text`, `time`) keep the
default `targeted_readback=True`; for their 1:1 registers the read-back is correct
(e.g. the `number` entity for `air_flow_rate_manual` displays that same register).

## 5. Optimistic UI rules

"Optimistic" = showing the requested/last-written value *before* the device confirms
it. Allowed **only** where the written register is 1:1 with the displayed state and
the value converges quickly (via targeted read-back or the trailing refresh).

Rules:

- Optimistic state is short-lived and must be **superseded by confirmed device
  state** as soon as it arrives (e.g. the fan's pending percentage self-expires on a
  TTL and clears once `supply_percentage`/`exhaust_percentage` match).
- Never invent optimistic values for measurements or safety/identity state.
- **Do not add new optimistic behaviour** as part of unrelated work; it is a
  deliberate, per-entity design decision.

### May use optimistic UI (control state, 1:1 with a write)

| Entity | Optimistic value |
|---|---|
| **fan** | `percentage` (pending-percentage after a confirmed airflow write; TTL-bounded, cleared on confirmed status) |
| **number** | setpoints (target values the user just set) |
| **switch** | control on/off state |
| **select** | current selected option |
| **climate** | `target_temperature`, `hvac_mode`, `fan_mode`, `preset_mode` |

### Must NOT use optimistic UI (status / measured / safety / identity)

These reflect the device's real state and must only ever show confirmed reads:

- `supply_air_flow` / `exhaust_air_flow`
- `supply_percentage` / `exhaust_percentage` **as status** (the fan's own display source)
- temperatures
- efficiency
- power
- heat recovery
- alarms / errors
- firmware / model / serial
- `device_clock`
- diagnostics

Rationale: an optimistic guess on any of these could hide a fault, misreport airflow,
or show a stale identity/clock value — all of which mislead the user and undermine
real-device trust.

## 6. Related tests

- `tests/test_write_readback.py` — read-back policy, success/read-fail/decode-fail
  outcomes, decoded-not-requested value, lock held during read-back,
  `targeted_readback` × `refresh` matrix, decode-failure never fails the write.
- `tests/test_fan.py` — no refresh between `mode`/`air_flow_rate_manual`, single
  refresh, `targeted_readback=False`, optimistic pending-percentage behaviour.
- `tests/test_climate.py` — every write path passes `targeted_readback=False` with
  one refresh per operation.
- `tests/test_services*.py` — service writes assert read-back disabled.

These run on **Python 3.13** with the HA test stack; verify in CI when the local
sandbox is older.
