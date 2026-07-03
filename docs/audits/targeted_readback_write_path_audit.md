# Targeted read-back write-path audit

- **Audit date:** 2026-07-03
- **Repo / branch:** `blakinio/thessla_green_modbus` @ `claude/targeted-readback-audit-ri433i` (based on `main`)
- **Scope:** targeted read-back and single-register write path *after* PR #1722.
- **Type:** documentation only. **No production code, tests, register maps, entity/unique/service IDs, or translation keys were changed.**

> **Important framing.** PR #1722 (`feat(coordinator): targeted read-back after successful register writes`, commit `9ac5601`, merged `490aba6` on 2026-06-15) introduced the behaviour described in the task. Since then, **two follow-up changes have already landed on the current tree**:
>
> - `6160586` — `fix(coordinator): disable targeted read-back for fan/climate/service writes` (2026-07-02 21:32 UTC)
> - PR #1726 (`readback-side-effects-fix`, merged `1417910`) and PR #1727 (`ha-version-compatibility`, merged `5b8319d`), both 2026-07-02 ~23:41.
>
> The real-device log quoted in the task (`2026-07-02 23:06:37…52`, ~15 s between `mode=1` and `air_flow_rate_manual=10`) is timestamped **before** those merges landed, so it reflects the **pre-fix PR #1722 code that was running on the user's device**, not the current tree. This audit therefore reports on the *current* code and distinguishes clearly between (a) issues already remediated and (b) issues still open.

---

## Executive summary

The most severe issues the task anticipates — the fan double-refresh between sequential writes, targeted read-back firing on fan/climate/service writes, and a bad read-back turning a successful write into a failure — **have already been fixed** in the current tree. The `Stage 1` hotfix the task proposes is, in substance, already implemented:

| Stage-1 hotfix item | Status in current tree |
|---|---|
| keyword-only `targeted_readback: bool = True` on `async_write_register` | **Done** — `schedule.py:361` |
| gate read-back on `targeted_readback and _targeted_readback_safe(...)` | **Done** — `schedule.py:401-405` |
| fan passes `targeted_readback=False` | **Done** — `fan.py:311` |
| fan avoids refresh between sequential writes; one refresh at end | **Done** — `fan.py:244-254`, `164-184` |
| climate manual-refresh paths pass `targeted_readback=False` | **Done** — `climate.py:201-217, 254-256` |
| services pass `targeted_readback=False` | **Done** — `dispatch.py:27-28, 179`; `handlers_maintenance.py:277-279` |
| decode/update failure never fails a successful write | **Done** — `schedule.py:425-443` |

**What remains open** is the item the task itself flags as `Stage 2`: the `_targeted_readback_safe` **policy is still too broad**. It is a deny-list over a permissive default (`function==3 and length==1 and not schedule_/setting_`), which still classifies a set of *dangerous configuration registers that are exposed as writable HA entities* as read-back-eligible:

- **Communication params (`communication_lockout` risk):** `uart_0_id`, `uart_1_id` (number); `uart_0_baud/parity/stop`, `uart_1_baud/parity/stop` (select).
- **Security (`security_lock` risk):** `lock_pass` (number, first word of a 2-word passphrase), `lock_flag` (switch), `access_level` (select).
- **Advanced config:** `configuration_mode` (select), `language` (select), `rtc_cal` (number).

Because these are written through the *simple-entity path* (`switch`/`number`/`select`), which still uses the default `targeted_readback=True`, they currently trigger a read-back on write. This is a **latent / correctness-of-policy** concern, **not** an observed failure. It is medium-priority hardening, not an emergency.

**Recommendation:** treat the observed fan bug as **already resolved** (verify on a real device once), and schedule the read-back policy narrowing (`Stage 2`) plus observability (`Stage 3`) as a follow-up. Do not broaden or further change the write path reactively.

---

## Current behavior

### Where targeted read-back is triggered

`ThesslaGreenModbusCoordinator.async_write_register` (`coordinator/schedule.py:354-445`). After a successful single-register write, still holding `_write_lock`:

```python
# schedule.py:400-417
_definition = self._resolve_write_definition(register_name)
if (
    targeted_readback
    and _definition is not None
    and _targeted_readback_safe(register_name, _definition)
):
    _raw_readback = await self._locked_read_holding_registers(
        _definition.address + offset, count=_definition.length,
    )
    if _raw_readback is not None:
        _readback_definition = _definition
        refresh_after_write = False
    else:
        _LOGGER.debug("Targeted read-back failed for %s; falling back to full refresh", ...)
```

`_targeted_readback_safe` (`schedule.py:45-58`):

```python
return (
    register_name not in _NO_READBACK_REGISTERS
    and definition.function == 3
    and definition.length == 1
    and not register_name.startswith(("schedule_", "setting_"))
)
```

The read (`_locked_read_holding_registers`, `schedule.py:479-518`) runs **under the write lock** so no other Modbus operation can interleave (prevents pymodbus transaction-ID mismatch on a shared TCP client). Decode + `async_set_updated_data` happen **outside** the lock (`schedule.py:425-443`) so listener notifications cannot re-enter the transport lock.

### Does `refresh=False` disable it? — **No. Confirmed from code.**

The read-back gate (`schedule.py:401-405`) depends only on `targeted_readback` and `_targeted_readback_safe(...)`. `refresh` is **not** part of that condition. `refresh` only governs:

- what `_handle_successful_single_register_write` returns as `refresh_after_write` (`schedule.py:256-272`), i.e. the **full-refresh fallback**, and
- whether the read-fail / decode-fail branches re-arm a full refresh (`schedule.py:415-417, 432-433`).

So `async_write_register(..., refresh=False)` **still performs a targeted read-back** if the register is `_targeted_readback_safe`. This matches the task's "important detail". The *only* switch that disables read-back is the new keyword-only `targeted_readback=False` (`schedule.py:361`). This is verified by the tests `test_targeted_readback_false_skips_locked_read` and `test_targeted_readback_default_true_still_reads_back` (`tests/test_write_readback.py:319-353`).

### What happens on each outcome

- **Read-back succeeds** (`_raw_readback is not None`): `refresh_after_write` is forced to `False`; the decoded value is written into a copy of `coordinator.data` and published via `async_set_updated_data` (`schedule.py:410-412, 434-443`). **No full refresh.** The value published is the **decoded device read-back**, not the requested value (proven by `test_targeted_readback_uses_decoded_value_not_raw_request`).
- **Read-back read fails** (`_locked_read_holding_registers` returns `None`): logged at debug; `refresh_after_write` stays equal to `refresh`, so a full refresh runs iff `refresh=True` (`schedule.py:413-417`; test `test_targeted_readback_fallback_when_read_fails`).
- **Decode fails after a successful read** (`schedule.py:426-433`): caught (`ValueError, TypeError, KeyError, IndexError, ArithmeticError`), logged at debug; if `refresh=True`, a full refresh is armed. `coordinator.data` is **not** mutated (test `test_targeted_readback_decode_failure_does_not_fail_write` / `..._refresh_false_no_full_refresh`).

### Can a successful Modbus write be reported as failed because read-back decode/update failed? — **No, in the current code.**

- `_locked_read_holding_registers` catches all Modbus/transport/attribute/type errors internally and returns `None` (`schedule.py:509-518`); it never raises into `async_write_register`.
- The decode + `async_set_updated_data` block is outside the lock and individually try/except-wrapped (`schedule.py:426-442`).
- The function returns via `finalize_write_result` (`write_path.py:116-120`), which returns `True` once the write succeeded.

Therefore no read-back failure path flips a successful write to `False`. (This was the specific regression PR #1726 closed; the two decode-failure tests lock it in.)

---

## Confirmed issues

**C1 — (RESOLVED) Fan refresh sandwiched between `mode` and `air_flow_rate_manual`.**
Root cause in PR #1722 code: `ThesslaGreenFan._write_register` defaulted `refresh=True` and each call ran its own `async_request_refresh()`, so a manual-mode percentage change became write→refresh→write→refresh. In the current tree, `async_set_percentage` writes both registers with `refresh=False` and issues **one** `async_request_refresh()` after both (`fan.py:244-254`). Regression-tested by `test_fan_set_percentage_manual_mode_no_refresh_between_writes` (`tests/test_fan.py:326-353`).

**C2 — (RESOLVED) Fan/climate/service writes triggered targeted read-back.**
All three paths now pass `targeted_readback=False` (see the per-path sections below). Tested across `test_write_readback.py`, `test_fan.py`, `test_climate.py`, and the `test_services_*` suite.

**C3 — (RESOLVED) A bad read-back could fail a successful write.**
Fixed by moving decode/update outside the lock with dedicated exception handling (`schedule.py:425-443`).

**C4 — (OPEN, medium) Read-back policy is a permissive deny-list, not an allow-list.**
`_targeted_readback_safe` treats *every* writable single-word holding register as eligible unless explicitly excluded. Dangerous configuration registers that are exposed as writable entities are therefore read-back-eligible today. See **Targeted read-back policy assessment**.

**C5 — (OPEN, low) Pre-existing optimistic mutations in `fan.async_turn_off`.**
`fan.py:202` and `fan.py:213` directly assign `coordinator.data[...] = 0` after a write. Pre-dates PR #1722. See **Fan write path**.

**C6 — (OPEN, low, cosmetic) Redundant definition resolution.**
`async_write_register` resolves the register definition twice — inside `_locked_single_register_write` and again at `schedule.py:400`. Harmless (cached lookup), noted for the eventual policy refactor.

---

## Fan write path

File: `custom_components/thessla_green_modbus/fan.py`.

### `_write_register` (`fan.py:280-318`) — read-back disabled, refresh caller-controlled
```python
kwargs = {"refresh": False, "targeted_readback": False}   # fan.py:311
...
success = await self.coordinator.async_write_register(register_name, int(value), **kwargs)
if refresh:
    await self.coordinator.async_request_refresh()
```
The fan's displayed percentage (`fan.percentage`) reads from **status** registers `supply_percentage`/`exhaust_percentage` (`fan.py:135-162`), which are *not* the setpoint registers it writes (`air_flow_rate_manual`, `mode`, `on_off_panel_mode`). A targeted read-back of a setpoint register would neither update the display nor be meaningful, so disabling it is correct. Verified by `test_fan_write_register_full_refresh_only` (asserts `read_holding_registers` is **not** called and exactly one refresh happens).

### Does the fan still trigger targeted read-back despite the "full-refresh-only" comment? — **No.** Confirmed by `targeted_readback=False` at `fan.py:311` and the test above.

### Does the fan refresh between `mode` and `air_flow_rate_manual`? — **No.**
`async_set_percentage` (`fan.py:221-272`), manual branch:
```python
if self._is_writable_holding_register("mode"):
    await self._write_register("mode", 1, refresh=False)            # fan.py:246
if self._is_writable_holding_register("air_flow_rate_manual"):
    await self._write_register("air_flow_rate_manual", actual_percentage, refresh=False)  # 249-251
if wrote_manual:
    await self.coordinator.async_request_refresh()                 # fan.py:254 — single refresh
```

### `async_turn_on` (`fan.py:164-190`)
Writes `on_off_panel_mode=1` with `refresh=False` (`fan.py:177`) then delegates to `async_set_percentage`, which performs the single trailing refresh. No double refresh — tested by `test_fan_turn_on_no_double_refresh`.

### `async_turn_off` (`fan.py:192-219`) — direct `coordinator.data` mutations (C5)
```python
await self._write_register("on_off_panel_mode", 0)   # refresh=True default → one refresh
self.coordinator.data["on_off_panel_mode"] = 0        # fan.py:202  (optimistic, same tick)
...
await self._write_register(register, 0)
self.coordinator.data[register] = 0                   # fan.py:213  (optimistic, same tick)
```
These are the **only** direct `coordinator.data[...] =` writes in the platform layer (grep-confirmed across `custom_components/`).

**Safe / risky / remove?** — **Safe to leave as-is; do not remove now.**
- They are *same-tick optimistic UI updates* that make `is_on` reflect the change before the debounced full refresh lands; the subsequent `async_request_refresh()` overwrites them with the real device value.
- They pre-date PR #1722 and are unrelated to the read-back regression.
- Removing them is out of scope: the task's hard rules forbid *adding* optimistic updates but say nothing about removing existing ones, and removing them would be a behaviour change (brief `is_on` flip-back) with no bug to justify it.
- Minor latent risk: they mutate the coordinator's dict in place rather than via `async_set_updated_data`, so listeners aren't notified until the refresh; acceptable because the refresh is already queued. **Recommendation: document, leave unchanged.**

### Minimal fix for the fan path
**None required** — the fan path is already correct. The only optional follow-up is to route the two optimistic writes through `async_set_updated_data` for listener consistency, which is *not* recommended as part of this hotfix.

---

## Climate write path

File: `custom_components/thessla_green_modbus/climate.py`. All logical operations already write with `refresh=False` + `targeted_readback=False` and issue exactly one `async_request_refresh()` at the end.

### `_write_register` (`climate.py:201-217`)
```python
return await self.coordinator.async_write_register(
    register, value, refresh=refresh, offset=0, targeted_readback=False)   # climate.py:212
```
(A `TypeError` fallback at `climate.py:214-217` re-issues the call without `offset` to tolerate patched/mock coordinators in tests — defensive, not a shim over production code.)

| Method | Registers written | `refresh=False`? | manual `async_request_refresh()`? | read-back? |
|---|---|---|---|---|
| `async_set_hvac_mode` (219-236) | `on_off_panel_mode`, `mode` | yes | yes (234) | disabled |
| `async_set_temperature` (238-262) | temporary block *or* `comfort_temperature` (254-256) + `required_temperature` | yes | yes (248/260) | disabled |
| `async_set_fan_mode` (264-275) | `air_flow_rate_manual` | yes | yes (271) | disabled |
| `async_set_preset_mode` (277-286) | `on_off_panel_mode`, `special_mode` | yes | yes (284) | disabled |
| `async_turn_on` (288-291) | `on_off_panel_mode` | yes | yes (291) | disabled |
| `async_turn_off` (293-296) | `on_off_panel_mode` | yes | yes (296) | disabled |

Note the direct call at `climate.py:254-256` (`comfort_temperature`) also explicitly passes `targeted_readback=False`, and the temporary paths use `async_write_temporary_temperature/airflow` (multi-register block, which has no read-back path at all).

### Should climate pass `targeted_readback=False` in manual-refresh paths? — **Yes, and it already does** (every path above). This is verified by `test_climate_write_paths_disable_targeted_readback` (`tests/test_climate.py:324-350`), which asserts `targeted_readback is False` on **every** `async_write_register` call and `async_request_refresh.await_count == 6`.

**Minimal fix:** none required.

---

## Service write paths

Files: `services/dispatch.py`, `services/handlers_maintenance.py`.

### `dispatch.write_register` (`dispatch.py:10-32`) — read-back disabled for all service register writes
```python
await coordinator.async_write_register(register, value, refresh=False, targeted_readback=False)  # 27-28
```
This is the shared `deps.write_register` used by *all* maintenance/parameter handlers (`handler_deps.py:31`), so `reset_filters`, `reset_settings`, `start_pressure_test`, `set_modbus_parameters`, mode/bypass/gwc parameter services all inherit `targeted_readback=False`. Each handler performs its own `refresh_and_log_success` (`dispatch.py:35-43`) afterward.

### `write_device_name_chunks` (`dispatch.py:167-182`)
Multi-register ASCII string written in offset chunks, each with `targeted_readback=False` (`dispatch.py:179`). `device_name` is also multi-word, so `_targeted_readback_safe` would return `False` anyway (`length != 1`), giving defence-in-depth.

### Maintenance handlers (`handlers_maintenance.py`)
| Service | Mechanism | Read-back |
|---|---|---|
| `reset_filters` (157-181) | `deps.write_register("filter_change", …)` | disabled (dispatch) — and `filter_change ∈ _NO_READBACK_REGISTERS` |
| `reset_settings` (184-212) | `write_register_batch` → `deps.write_register` (`hard_reset_settings`, `hard_reset_schedule`) | disabled — both also in `_NO_READBACK_REGISTERS` |
| `start_pressure_test` (215-237) | `write_register_batch` (`pres_check_day_2`, `pres_check_time_2`) | disabled — both also in `_NO_READBACK_REGISTERS` |
| `set_modbus_parameters` (240-267) | `write_mapped_optional_register` → `deps.write_register` (`uart_*`) | disabled (dispatch) |
| `set_device_name` (270-298) | long names: direct `async_write_register(..., targeted_readback=False)` (277-279); short: `write_device_name_chunks` | disabled |
| `sync_time` (301-325) | `async_write_registers(start_address=0, _clock_payload)` | **N/A** — multi-register path has no read-back |
| `sync_device_clock` (328-361) | `async_perform_clock_sync` (clock_sync.py) | via multi-register write — no read-back |

### Should service writes trigger targeted read-back at all? — **No, and they don't.**
Service writes target destructive/trigger registers (`hard_reset_*`, `pres_check_*`, `filter_change`), communication params (`uart_*`), string blocks (`device_name`), and clock registers (`date_time*` via `sync_time`). For all of these a read-back is either misleading (reset/trigger registers self-clear to 0), impossible in a 1-word read (multi-register clock/name), or dangerous to issue on a link whose parameters were just changed (`uart_*`). The current code correctly forces `targeted_readback=False`. Tested by e.g. `test_services_handlers_parameters.py:228`, `test_services_handlers_maintenance.py:108`, `test_services.py:111-112`, `test_services_dispatch_validation.py:192-195`, `test_services_handlers_modes.py:99`, `test_services_handlers_parameters_bypass.py:61`, `test_services_handlers_parameters_gwc.py:61`.

**Recommendation:** confirm the current default is retained. No change required.

---

## Simple entity paths

These platforms write through `ThesslaGreenEntity._write_register` (`entity.py:100-122`), which uses `refresh=True` and does **not** override `targeted_readback` → the coordinator default (`True`) applies, so **targeted read-back is active** for eligible registers.

| Platform | Write entry | Read-back active? | Classification |
|---|---|---|---|
| `switch` | `switch.py:189-206` → `super()._write_register` | yes (holding); coils excluded by `function!=3` | **mostly safe**; unsafe subset = `lock_flag` |
| `number` | `number.py:202-218` → `super()._write_register` | yes | **safe for setpoints** (`air_flow_rate_manual`, temps); **unsafe subset** = `uart_*_id`, `lock_pass`, `rtc_cal` |
| `select` | `select.py:145-167` → `self._write_register` | yes; `schedule_`/`setting_` excluded by prefix | **safe for enum control**; **unsafe subset** = `uart_*_baud/parity/stop`, `access_level`, `configuration_mode` |
| `text` | `text.py:120-128` | eligible, but `device_name` is multi-word → `_targeted_readback_safe` returns `False` | **safe** (excluded by `length!=1`) |
| `time` | `time.py:126-140` | eligible, but BCD time slots use `schedule_`/`setting_` prefixes → excluded | **safe** (excluded by prefix); ambiguous if any non-prefixed BCD-time register is exposed |

### Detail on the checked cases

- **`number: air_flow_rate_manual`** — the *number* entity displays `coordinator.data["air_flow_rate_manual"]` directly (`number.py:188-200`), so for this entity the register **is** 1:1 write=status and read-back is correct. (Contrast with the *fan*, where the same register is a setpoint, not the display source — which is exactly why the fan disables read-back.) **Safe via the number path.**
- **`text: device_name`** — multi-register ASCII string; `definition.length > 1` → excluded from read-back (unit-tested: `test_targeted_readback_safe_multi_register_excluded`). **Safe.**
- **`time` / schedule writes** — BCD HH:MM schedule slots carry `schedule_`/`setting_` prefixes and are excluded (`test_targeted_readback_safe_schedule_excluded`, `..._setting_excluded`). **Safe.** *Ambiguity:* if a future non-prefixed BCD/clock register were exposed as a `time` entity it would silently become read-back-eligible — an argument for the allow-list refactor (Stage 2).
- **`select` schedule/setting** — same prefix exclusion. **Safe.**
- **Dangerous config entities with `risk_level`/`risk_category`/`safety_warning`** — these are the open concern (C4). See next section.

---

## Targeted read-back policy assessment

### Current policy (`schedule.py:45-58`) restated

`_targeted_readback_safe` = eligible **iff** `name ∉ _NO_READBACK_REGISTERS` **and** `function == 3` **and** `length == 1` **and** `name` does not start with `schedule_`/`setting_`.

`_NO_READBACK_REGISTERS` (`schedule.py:30-42`): `hard_reset_settings`, `hard_reset_schedule`, `filter_change`, `airflow_rate_change_flag`, `temperature_change_flag`, `cfg_mode_1`, `cfg_mode_2`, `pres_check_day_2`, `pres_check_time_2`.

### Is it too broad? — **Yes.** It is a deny-list over a permissive default; anything not enumerated is eligible.

I inventoried the bundled register set (`registers/thessla_green_registers_full.json`, 357 registers; 280 writable holding function-03 registers) and cross-referenced against the entity mappings. Findings for the categories the task calls out:

| Category | Writable-holding regs | Exposed as writable entity? | Read-back eligible **today**? | Real risk of read-back |
|---|---|---|---|---|
| **`e_*` alarm/status** | 32 | No — mapped as **diagnostic binary_sensors** (`_static_discrete_diagnostics.py`; `_mapping_extend_common.py:28` classifies `e_/s_/f_` as read-only) | eligible *if written*, but **never written via an entity** | none in practice (no write path) |
| **`s_*` status** | 23 | No (read-only display) | same | none in practice |
| **`f_*` flags** | 4 | No (read-only display) | same | none in practice |
| **`date_time*` clock** | 4 | No single-word entity; written as a **block** via `sync_time` (`async_write_registers`) | block write ⇒ no read-back path | none (no single-register write path) |
| **`rtc_cal`** | 1 | **Yes — number** (`_static_numbers.py:121`) | **yes** | low (1:1 with the number's own display) |
| **`uart_*` comms** | 8 | **Yes** — `uart_*_id` number (`_static_numbers.py:97,107`); `uart_*_baud/parity/stop` select (`_static_discrete_uart.py`) | **yes** | **medium** — read-back issued on a link whose serial params may have just changed; risk of failed/garbled read |
| **`lock_*` security** | `lock_pass`, `lock_pass_2`, `lock_flag` | `lock_pass` **number** (`_static_numbers.py:123`); `lock_flag` **switch** (`_static_discrete.py:382`) | **yes** | **medium** — device may not echo written security values; read-back can publish a masked/misleading value; `lock_pass` is only the **first word** of a 2-word passphrase (partial view of a logical multi-register value) |
| **`access_level`** | 1 | **Yes — select** (`_static_discrete.py:96`) | **yes** | low–medium (device may reject/auto-revert; read-back reflects actual, which is arguably desirable, but semantics are sensitive) |
| **`configuration_mode`** | 1 | **Yes — select** (`_static_discrete.py:82`) | **yes** | low (1:1 display) but puts the unit into a special mode; read-back itself is benign |
| **`language`** | 1 | **Yes — select** (`_static_discrete.py:125`) | **yes** | low (benign, 1:1) |
| **`filter_change`** (destructive select) | 1 | Yes — select | **No** — in `_NO_READBACK_REGISTERS` | correctly excluded ✓ |

**Interpretation.** The policy's biggest real weaknesses are the **`uart_*`** and **`lock_*`/`access_level`** groups: they are writable entities (so a read-back *does* fire on user action), and they are exactly the registers where an immediate same-connection read-back is least trustworthy (comms just reconfigured, or security value not echoed). `lock_pass` additionally illustrates the **"single-register fragment of a logical multi-register value"** problem: reading back only word 1 of the passphrase.

The `e_*/s_*/f_*` "write-to-clear" concern is **theoretical** in this build: those registers are exposed read-only (binary sensors), so no entity write path reaches them. They would only matter if a future service or entity started writing them — another argument for switching to an allow-list so the default is *deny*.

### Fan/climate setpoint-vs-status case
`air_flow_rate_manual`, `mode`, `on_off_panel_mode` are setpoints whose *fan* display is derived from other status registers. These are already handled by the fan/climate `targeted_readback=False` opt-out, so the policy breadth does not affect them through those entities. (Through the `number`/`select` entities they are 1:1 and safe.)

### Recommendation (documentation only — do not implement here)
Migrate `_targeted_readback_safe` from a **deny-list** to an **allow-list / category** model where only registers *known* to be 1:1 write=status are eligible, and everything else (comms, security, config-mode, clock, reset/trigger, multi-register fragments) defaults to full-refresh-only. In the interim, the cheapest correct narrowing is to add the dangerous groups to `_NO_READBACK_REGISTERS` (or exclude by `risk_category ∈ {communication_lockout, security_lock, advanced_configuration}` / by `uart_`/`lock_`/`access_level`/`configuration_mode` name predicates). This is **Stage 2** below; it is *not* required to resolve the observed device issue.

---

## Test coverage gaps

Current coverage is already strong. Existing, relevant tests:

- **Policy unit tests** — `tests/test_write_readback.py:73-104` (`holding_single`, `coil_excluded`, `multi_register_excluded`, `no_readback_register`, `schedule_excluded`, `setting_excluded`).
- **Coordinator read-back behaviour** — `test_write_readback.py:111-459`: success updates data & no refresh; read-fail ⇒ full refresh; decoded (not requested) value published; write-fail ⇒ `False` and no read attempt; `_NO_READBACK`/coil/multi-register skip read-back; lock held during read-back; `targeted_readback` True/False × `refresh` True/False matrix; **decode-failure does not fail the write** (both refresh states).
- **Entity base** — `test_write_readback.py:467-534`: `_write_register` delegates refresh policy to the coordinator.
- **Fan** — `test_write_readback.py:542-586` (read-back disabled, refresh honoured) + `tests/test_fan.py:326-391` (no refresh between `mode`/`air_flow_rate_manual`; single refresh; `turn_on`/`turn_off` refresh counts; `targeted_readback=False` asserted).
- **Climate** — `tests/test_climate.py:324-350` asserts every write path passes `targeted_readback=False` with one refresh per operation.
- **Services** — read-back-disabled asserted in `test_services*` (device_name, filter_change, special_mode, bypass_mode, gwc_mode).

### Answers to the task's specific test questions
1. **Do tests assert the fan does not call `_locked_read_holding_registers`?** — **Yes**, indirectly but decisively: `test_fan_write_register_full_refresh_only` asserts `client.read_holding_registers.assert_not_called()` (the concrete read that `_locked_read_holding_registers` performs).
2. **Do tests only assert refresh, while read-back may still happen?** — **No**; fan/climate tests assert both `targeted_readback=False` *and* the refresh count, and coordinator tests assert `read_holding_registers` is/ isn't called.
3. **Are climate manual-refresh paths tested?** — **Yes** (`test_climate.py:324-350`).
4. **Are service writes tested with read-back disabled?** — **Yes** (multiple `test_services_*` assertions listed above).
5. **Is decode failure after read-back tested?** — **Yes** (`test_targeted_readback_decode_failure_does_not_fail_write` and the `refresh_false` variant).
6. **Are simple switch/number/select regressions tested?** — **Partially**; base-class delegation is tested via `ThesslaGreenEntity._write_register`, but there is no test that exercises `switch`/`number`/`select` `async_*` methods end-to-end specifically for read-back behaviour.

### Missing / recommended tests (to add *with* the Stage 2 policy change, not now)
- **M1 — dangerous-config read-back skip:** parametrised test that writing `uart_0_baud` / `uart_0_id` / `lock_pass` / `lock_flag` / `access_level` / `configuration_mode` via their entity does **not** perform a targeted read-back (once the policy narrows). Today these *would* read back; a test asserting the desired end-state should land with the policy change.
- **M2 — number `air_flow_rate_manual` positive case:** assert that the *number* entity (unlike the fan) *does* read back and publishes the decoded value (documents the intended 1:1 behaviour and guards against an over-broad exclusion).
- **M3 — select schedule/setting integration:** assert `select.async_select_option` on a `schedule_`/`setting_` register does not read back (currently only the policy predicate is unit-tested, not the select path).
- **M4 — `time` entity path:** assert a BCD `time` write does not read back (guards the prefix exclusion at the entity level).
- **M5 — fan optimistic-mutation guard:** assert `async_turn_off` leaves `coordinator.data["on_off_panel_mode"] == 0` after the write (documents C5 so it isn't accidentally removed).
- **M6 — `lock_pass` multi-word fragment:** explicit test/documentation that read-back of a single word of a logical 2-word value is undesirable (drives M1).

---

## Recommended staged implementation

> Proposal only. Nothing in this section was implemented in this task.

### Stage 0 — verify the already-shipped hotfix on a real device (do first)
The Stage-1 items are already merged. Before writing more code, reproduce the original scenario on hardware (change fan %; confirm a *single* `air_flow_rate_manual` write with no intervening refresh, and no `Successfully wrote … to register mode` / `air_flow_rate_manual` pair separated by ~15 s). Record evidence in `docs/real_device_validation.md`. **Low risk, high value.**

### Stage 1 — focused hotfix — **ALREADY DONE** (documented for completeness)
- keyword-only `targeted_readback=True` on `async_write_register` — `schedule.py:361` ✔
- gate on `targeted_readback and _targeted_readback_safe(...)` — `schedule.py:401-405` ✔
- fan passes `targeted_readback=False` — `fan.py:311` ✔
- fan: no refresh between sequential writes, one refresh at end — `fan.py:244-254` ✔
- climate manual-refresh paths pass `targeted_readback=False` — `climate.py:201-217, 254-256` ✔
- services pass `targeted_readback=False` — `dispatch.py:27-28, 179`; `handlers_maintenance.py:277-279` ✔
- decode/update failure never fails a successful write — `schedule.py:425-443` ✔

No further Stage-1 work is required. If anything, add regression test **M5** to pin the fan optimistic-update behaviour.

### Stage 2 — read-back policy refactor (the real open work)
- Extract the policy into a dedicated helper/module (e.g. `coordinator/readback_policy.py`) so it is independently testable and does not live inside the write mixin.
- Replace the permissive deny-list with an **allow-list / category** model: eligible only when the register is *known* 1:1 write=status. Drive exclusion of `uart_*`, `lock_*`, `access_level`, `configuration_mode`, `language`, `rtc_cal`, and any `date_time*`/multi-register fragment either by name predicate or (better) by the `risk_category` metadata already present in the entity mappings (`communication_lockout`, `security_lock`, `advanced_configuration`, `destructive_action`).
- Land tests **M1–M4, M6** alongside the change.
- **Constraint:** do not change register names/addresses, entity/unique/service IDs, or translation keys; this is purely an internal policy predicate.

### Stage 3 — observability
- Add success / failure / skipped counters for read-back (surface via `diagnostics.py`).
- Emit a `warning` after N consecutive read-back failures for the same register (helps spot devices/firmware that never echo a value).
- Optional internal kill switch (config/const flag, *not* a user-facing options-flow change) to disable targeted read-back globally if a field regression appears.

---

## Risk assessment

| Recommendation | Risk | Why |
|---|---|---|
| **Stage 0** — real-device verification of shipped hotfix | **Low** | Read-only observation; no code change. Highest value per effort. |
| **Stage 1** — already implemented | **Low** (already merged, well-tested) | Behaviour is covered by ~30 targeted tests; nothing left to change. |
| **Add regression test M5** (fan optimistic-update) | **Low** | Test-only; documents existing behaviour. (Note: task forbids changing tests in *this* audit — schedule for the follow-up PR.) |
| **Stage 2** — allow-list policy narrowing (name-predicate interim) | **Medium** | Touches the shared write path used by every entity/service. A too-aggressive exclusion could send benign 1:1 registers back to full-refresh (slower, but *correct*); a too-narrow one leaves a dangerous register eligible. Must be landed with M1–M4/M6 and a real-device pass. Mitigated by being an internal predicate only. |
| **Stage 2** — full module extraction + metadata-driven policy | **Medium** | Same blast radius plus a structural move; must preserve `_NO_READBACK_REGISTERS` semantics and layer isolation. Do as one reviewed slice. |
| **Stage 3** — counters/warnings | **Low** | Additive diagnostics; no write-path behaviour change. |
| **Stage 3** — internal kill switch | **Medium** | Introduces a config surface; risk of it being toggled unexpectedly or interacting with options flow. Keep it a `const`/internal flag, not an options-flow entry, to stay within the hard rules. |
| **Removing fan `async_turn_off` optimistic mutations (C5)** | **Medium**, **not recommended** | No bug justifies it; removal is a user-visible behaviour change (brief `is_on` flip-back) and risks reintroducing exactly the kind of UI lag the mutation avoids. Leave unchanged. |

---

## Validation run

Environment: **Python 3.11.15**, `ruff 0.15.8`. `pytest`, `pydantic`, and `homeassistant` are **not installed** in this sandbox. Per `CLAUDE.md` §2, when pytest cannot run on 3.13 the remaining checks are run and the pytest gap is flagged for CI.

| Command | Result |
|---|---|
| `python -m compileall -q custom_components/thessla_green_modbus tests tools` | **PASS** (compileall OK) |
| `ruff check custom_components tests tools` | **PASS** ("All checks passed!") |
| `ruff check --select I custom_components tests tools` | **PASS** ("All checks passed!") |
| `ruff format --check custom_components tests tools` | **PASS** (450 files already formatted) |
| `pytest --collect-only -q` | **NOT RUN** — `No module named pytest` |
| `pytest tests/ -q` (full suite) | **NOT RUN** — pytest/pydantic/homeassistant absent; requires Python 3.13 CI |
| `tools/check_translations.py` | **PASS** ("All translation keys present.") |
| `tools/validate_entity_mappings.py` | **NOT RUN** — `ModuleNotFoundError: pydantic` |
| `tools/compare_registers_with_reference.py` | Runs; reports pre-existing informational name mismatches (unrelated to this audit — no code changed) |

**Flag (explicit):** `pytest --collect-only` and the full `pytest` suite **were not run** in this sandbox because the interpreter is Python 3.11 and `pytest`/`pydantic`/`homeassistant` are unavailable. **Full pytest must be verified in CI on Python 3.13.** This task changes no code or tests, so it introduces no new behaviour for pytest to cover; the existing suite (see *Test coverage gaps*) already exercises the read-back paths.

---

## Final recommendation

**Fix immediately:**
- Nothing new in production code. The observed fan double-refresh / stray read-back / read-back-fails-the-write issues are **already fixed** on the current tree (commit `6160586`, PRs #1726/#1727). The single immediate action is **Stage 0**: reproduce the fan-percentage change on a real device and record the evidence — confirming the shipped fix resolves the reported log symptom.

**Should wait (next PR, not this one):**
- **Stage 2** — narrow `_targeted_readback_safe` from a deny-list to an allow-list/category model so that `uart_*`, `lock_*`, `access_level`, `configuration_mode`, and multi-register fragments (`lock_pass`, `date_time*`) are no longer read-back-eligible via their entities. Ship with tests **M1–M4, M6** and a real-device pass. This is hardening of a **latent** policy weakness, not a live incident.
- **Stage 3** — add read-back success/failure/skipped diagnostics and a warning-after-repeated-failures signal; keep any kill switch internal (no options-flow change).
- Add regression test **M5** for the fan optimistic-update behaviour when the Stage 2 PR touches this area.

**Should NOT be changed yet:**
- Do **not** remove the `fan.async_turn_off` optimistic `coordinator.data` mutations (`fan.py:202, 213`) — no bug justifies it and removal is a behaviour change.
- Do **not** add optimistic updates anywhere, alter register addresses/names, entity/unique/service IDs, translation keys, or config/options-flow behaviour.
- Do **not** broaden the write path or reintroduce `dev`, `modbus_helpers.py`, or compatibility shims.
- Do **not** change the `{16, 8192}` batch boundaries or raise `quality_scale` (gated on real-device validation).

**Bottom line:** the write path is in good shape post-#1726/#1727; the only substantive open item is the *breadth* of the read-back eligibility policy for dangerous configuration entities, which is a medium-risk, test-backed follow-up — not an emergency and not something to change reactively.
