# Home Assistant Quality Scale Audit

**Date:** 2026-05-09
**Branch:** dev (working branch: claude/setup-dev-workflow-yd3k6)
**Python version:** 3.13.12
**Project version:** 2.8.0
**Integration:** `thessla_green_modbus` — ThesslaGreen Modbus (Modbus TCP/RTU local hub)

---

## Summary Verdict

| Tier | Verdict | Notes |
|---|---|---|
| Architecture Alignment | PASS | Clean layered architecture; scanner/transport/core HA-free |
| Bronze | PASS | All Bronze requirements met |
| Silver | PARTIAL | Most Silver met; `repairs.py` is stub; real-device not proven |
| Gold | PARTIAL | Diagnostics download present; real-device validation not proven; discovery present |

---

## 1. Validation Evidence

All gates run locally with Python 3.13.12.

| Gate | Command | Result |
|---|---|---|
| ruff check | `ruff check custom_components tests tools` | PASS — All checks passed |
| ruff import-order | `ruff check --select I custom_components tests tools` | PASS — All checks passed |
| ruff format | `ruff format --check custom_components tests tools` | PASS — 419 files already formatted |
| compileall | `python3.13 -m compileall -q custom_components tests tools` | PASS |
| compare_registers | `python3.13 tools/compare_registers_with_reference.py` | PASS (exit 0; 62 vendor-extension extras expected) |
| check_maintainability | `python3.13 tools/check_maintainability.py` | PASS — Maintainability gate passed |
| validate_entity_mappings | `python3.13 tools/validate_entity_mappings.py` | PASS — OK: 366 entities validated |
| pytest | `python3.13 -m pytest tests/` | PASS — **1948 passed, 4 skipped** |

### Import gate

```
OK pydantic: 2.12.2
OK pytest: 9.0.3
OK pytest_asyncio: 1.3.0
OK pytest_homeassistant_custom_component: installed
OK homeassistant: installed
```

### Final invariants

| Invariant | Result |
|---|---|
| `coordinator.__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]` | PASS |
| Top-level `coordinator.py` absent | PASS |
| No HA imports in `scanner/` | PASS (scanner HA imports: clean) |

---

## 2. Metadata Evidence

| Field | Value | Status |
|---|---|---|
| manifest domain | `thessla_green_modbus` | PASS |
| manifest name | `ThesslaGreen Modbus` | PASS |
| manifest version | `2.8.0` | PASS |
| pyproject version | `2.8.0` | PASS — versions match |
| manifest homeassistant | `2026.1.0` | PASS |
| manifest integration_type | `hub` | PASS |
| manifest iot_class | `local_polling` | PASS |
| manifest config_flow | `true` | PASS |
| manifest quality_scale | `silver` | PASS (claimed) |
| manifest codeowners | `["@blakinio"]` | PASS |
| manifest requirements | `["pymodbus>=3.6.0"]` | PASS |
| manifest documentation | `https://github.com/blakinio/thesslagreen` | PASS |
| manifest issue_tracker | `https://github.com/blakinio/thesslagreen/issues` | PASS |
| manifest after_dependencies | `["modbus"]` | PASS |
| manifest loggers | `["custom_components.thessla_green_modbus"]` | PASS |
| manifest dhcp | hostname+macaddress patterns | PASS |
| manifest zeroconf | `_modbus._tcp.local.` with model property | PASS |
| manifest files | all referenced files listed | PASS |
| hacs.json present | yes | PASS |
| hacs.json name | `ThesslaGreen Modbus` | PASS |
| hacs.json content_in_root | `false` | PASS |
| hacs.json render_readme | `true` | PASS |
| pyproject requires-python | `>=3.13` | PASS |
| **Overall** | — | **metadata consistency OK** |

---

## 3. Architecture Alignment Rules

| Rule | Status | Evidence | Missing / Follow-up |
|---|---|---|---|
| Integration uses config flow (not YAML-only setup) | PASS | `manifest.json: config_flow=true`; `ConfigFlow` class in `config_flow.py` | — |
| Integration is a hub type | PASS | `manifest.json: integration_type=hub` | — |
| IoT class is `local_polling` | PASS | `manifest.json: iot_class=local_polling` | — |
| No blocking I/O in event loop | PASS | Transport uses `asyncio`, `await`; all I/O async | — |
| HA not imported in transport/scanner/core layers | PASS | `rg` confirmed zero HA imports in `scanner/`, `transport/`, `core/`, `registers/` | — |
| Coordinator pattern used | PASS | `coordinator/coordinator.py` extends HA DataUpdateCoordinator | — |
| Entity state from coordinator (no direct I/O in entities) | PASS | Entities read from `coordinator.data`; no transport calls | — |
| Services implemented correctly | PASS | `services.yaml` + `services.py` + handlers; `async_setup_services`/`async_unload_services` | — |
| `__all__` on coordinator package | PASS | `coordinator/__init__.py` exports `["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]` | — |
| No proxy/re-export-only modules | PASS | `refactor_status.md` documents all constraints enforced | — |

---

## 4. Bronze Rules

| Rule | Status | Evidence | Missing / Follow-up |
|---|---|---|---|
| Config flow exists | PASS | `config_flow.py`; `ConfigFlow` class; `async_step_user`, `async_step_confirm`, `async_step_dhcp`, `async_step_zeroconf` | — |
| Config flow tested | PASS | `tests/test_config_flow_user*.py`, `test_config_flow_errors.py`, `test_config_flow_confirm.py`, `test_config_flow_options.py`, `test_config_flow_reauth.py`, `test_optimized_integration_setup.py` | — |
| Manifest required fields present | PASS | All required fields verified in Section 2 | — |
| Unique IDs assigned to entries | PASS | `async_set_unique_id` + `_abort_if_unique_id_configured` in all setup paths; `build_unique_id` uses host:port:slave_id | — |
| Entities have stable unique IDs | PASS | `entity.py` property derives `unique_id` from `device_unique_id_prefix` + register name; migration via `unique_id_migration.py` | — |
| Unique ID migration path exists | PASS | `_entry_migrations.py`, `unique_id_migration.py`, `async_migrate_entity_unique_ids` in `_setup.py` | — |
| Devices and entities registered correctly | PASS | `coordinator_diagnostics.py: get_device_info()` returns `DeviceInfo`; entity `unique_id` derived from coordinator device prefix | — |
| Integration can be unloaded | PASS | `async_unload_entry` in `__init__.py` calls `async_unload_platforms` + `coordinator.async_shutdown()` + `async_unload_services` | — |
| Unload tested | PASS | `tests/test_services_handlers_targets.py: test_async_unload_services`; `test_optimized_integration_setup.py` | — |
| Setup failures handled with `ConfigEntryNotReady` | PASS | `_setup.py` catches `(TimeoutError, ConnectionException, ModbusException, UpdateFailed, OSError)` and raises `ConfigEntryNotReady` | — |
| Common connection failures handled | PASS | `_setup.py` catches `TimeoutError`, `ConnectionException`, `ModbusIOException`, `OSError` | — |
| Runtime exceptions don't crash HA | PASS | `UpdateFailed` used via `coordinator/errors.py`; `CancelledError` re-raised; `sensor.py` catches `CancelledError` | — |
| Basic documentation exists | PASS | `README.md` covers: requirements, supported devices, installation, config flow, services, diagnostics, troubleshooting | — |
| Translations exist (en) | PASS | `translations/en.json` with `config`, `options`, `entity`, `diagnostics`, `issues`, `services` sections | — |
| Translations exist (pl) | PASS | `translations/pl.json` mirrors `en.json` structure | — |
| Config flow strings cover user/confirm/reauth/reconfigure | PASS | All four steps present in both `en.json` and `pl.json` | — |
| Dependencies declared correctly | PASS | `manifest.json: requirements=["pymodbus>=3.6.0"]`; no other runtime deps | — |
| `after_dependencies` used correctly | PASS | `["modbus"]` declared | — |
| Tests exist for config flow and entities | PASS | 1948 tests pass covering config_flow, sensor, binary_sensor, number, select, switch, fan, climate, text, time entities | — |

---

## 5. Silver Rules

| Rule | Status | Evidence | Missing / Follow-up |
|---|---|---|---|
| Active codeowners | PASS | `manifest.json: codeowners=["@blakinio"]` | — |
| Strict typing (`from __future__ import annotations`) | PASS | 80/83 integration root `.py` files use `from __future__ import annotations`; `mypy` config in `pyproject.toml` with `disallow_untyped_defs=true` | Consider enforcing mypy in CI |
| Robust error handling | PASS | `ConfigEntryNotReady`, `UpdateFailed`, `CancelledError` all handled; backoff/retry/reconnect in transport layer | — |
| Retry / reconnect / backoff behavior | PASS | `_transport_retry.py`, `modbus_transport_base.py`: exponential backoff with jitter; `transport/retry.py: calculate_backoff`; `_apply_backoff`, `_handle_timeout`, `reconnect` on errors | — |
| Device unavailable / recovery | PASS | `sensor.py: available` property; coordinator sets `available=False` on errors; recovery on next successful poll | — |
| Log spam avoidance | PASS | `error_policy.py: should_log_timeout_traceback` controls traceback verbosity; configurable log level in options flow | — |
| Reauth flow | PASS | `async_step_reauth`, `async_step_reauth_confirm` implemented; `entry.async_start_reauth(hass)` triggered on auth failure | — |
| Reconfigure flow | PASS | `async_step_reconfigure` implemented; `build_reconfigure_schema` in `config_flow_schema.py` | — |
| Options flow | PASS | `OptionsFlow` class in `config_flow.py`; configures scan interval, timeout, retry, log level, transport, deep/safe scan, skip missing registers | — |
| Repairs (if applicable) | PARTIAL | `repairs.py` exists but is a scaffold stub: `"""TODO: module scaffold for branch test refactor."""` No `async_create_issue` calls found | Implement actual repairs or remove stub |
| Diagnostics download | PASS | `diagnostics.py: async_get_config_entry_diagnostics` implemented; `strings.json` has `diagnostics` section; tested in `test_diagnostics.py` | — |
| Docs troubleshooting section | PASS | `README.md: ## Diagnostyka i problemy` covers debug logging, diagnostics download, Modbus conflicts | English troubleshooting section absent (README is Polish-primary) |
| Docs supported devices/features | PASS | `README.md` lists supported transports, devices, entity types | — |
| Tests cover error paths | PASS | `test_config_flow_errors.py`, `test_coordinator_error_paths.py`, `test_coordinator_error_paths_split.py`, `test_coordinator_errors.py`, `test_scanner_error_paths.py`, `test_optimized_integration_errors.py`, `test_modbus_transport_errors.py` | — |
| Entities use appropriate device_class | PASS | `sensor.py`, `binary_sensor.py` assign `_attr_device_class` from mapping definitions; `BinarySensorDeviceClass`, `SensorDeviceClass` used | — |
| Entities use appropriate state_class | PASS | `sensor.py` assigns `_attr_state_class` from mapping definitions | — |
| Entities use appropriate entity_category | PASS | `sensor.py`, `binary_sensor.py` assign `EntityCategory.DIAGNOSTIC` for diagnostic/alarm entities | — |
| `disabled_by_default` where appropriate | UNKNOWN | Not found in entity or mapping code; diagnostic entities use `entity_category=DIAGNOSTIC` but no `disabled_by_default=True` found | Verify if diagnostic/rarely-used entities are disabled by default |
| No HA imports in scanner/transport | PASS | Confirmed by `rg` check — zero HA imports in `scanner/`, `transport/`, `core/`, `registers/` | — |
| CI gates meaningful | PASS | CI: `ruff check`, `compileall`, `compare_registers`, `check_maintainability`, `validate_entity_mappings`, `pytest --cov`, `hassfest`, `hacs/action` | — |
| HACS validation | UNKNOWN | CI job added (`hacs/action@main`); not run locally; awaiting first CI run result | Run CI and record result |
| hassfest validation | UNKNOWN | CI job added (`home-assistant/actions/hassfest@main`); not run locally; awaiting first CI run result | Run CI and record result |

---

## 6. Gold Rules

| Rule | Status | Evidence | Missing / Follow-up |
|---|---|---|---|
| DHCP discovery | PASS | `manifest.json: dhcp` with `hostname=airpack*`, `macaddress=00:80:F4:*`; `async_step_dhcp` in config flow | — |
| Zeroconf discovery | PASS | `manifest.json: zeroconf` with `_modbus._tcp.local.` and model filter; `async_step_zeroconf` in config flow | — |
| Reconfigure flow (Gold-level) | PASS | `async_step_reconfigure` uses `async_update_reload_and_abort`; reconfigure step in `translations/en.json` | — |
| Diagnostics download (confirmed) | PASS | `diagnostics.py` tested with 8 test functions covering: last_scan, additional fields, unknown registers, raw registers, anomalies, JSON serializable, translation errors, redaction | — |
| Repairs flow | PARTIAL | `repairs.py` is a stub; no `async_create_issue` or issue-type definitions | Implement or remove stub |
| Full docs (Gold-level) | PARTIAL | README in Polish; no English README; no dedicated docs site; troubleshooting present | Add English documentation |
| High coverage: config flow | PASS | 10+ test files cover config flow (user, TCP, RTU, errors, confirm, reauth, options, reconfigure, duplicate, validation) | — |
| High coverage: options/unload/reload | PASS | `test_config_flow_options.py`; `async_unload_entry` tested; `async_migrate_entry` covered | — |
| Entity/device registry correctness | PASS | `test_entity_unique_id.py`, `test_cleanup_old_entities.py`, `test_migrate_unique_id.py` | — |
| Stale device handling | PASS | `test_cleanup_old_entities.py` exists; unique ID migration handles legacy ID formats | — |
| Translations completeness | PASS | `en.json` and `pl.json` both present; `test_translations.py`, `test_strings_translations.py`, `test_unused_translations.py` | — |
| Release process | PARTIAL | `CHANGELOG.md` exists; CI gates pass; no GitHub release tag `v2.8.0` created yet; no HACS listing confirmed | Create `v2.8.0` release tag after CI green |
| HACS validation (confirmed run) | UNKNOWN | CI job exists; not confirmed run; awaiting CI execution | Confirm CI result |
| hassfest validation (confirmed run) | UNKNOWN | CI job exists; not confirmed run; awaiting CI execution | Confirm CI result |
| Real-device validation evidence | UNKNOWN | `docs/real_device_validation.md` is a checklist template — no evidence from a physical device | Test on a real ThesslaGreen AirPack and complete evidence record |

---

## 7. Recommended Follow-up PRs

### P0 — Release Blockers

| # | Issue | Action |
|---|---|---|
| P0-1 | HACS and hassfest CI results unconfirmed | Push PR, confirm CI green, record results in `docs/release_readiness.md` |
| P0-2 | No GitHub release tag for 2.8.0 | Create `v2.8.0` tag and GitHub release after CI green and device validation |
| P0-3 | Real-device validation not proven | Test on physical ThesslaGreen AirPack; complete `docs/real_device_validation.md` evidence record |

### P1 — Silver / Gold Gaps

| # | Issue | Action |
|---|---|---|
| P1-1 | `repairs.py` is a stub | Either implement a repairs flow (e.g., for config migration issues or persistent auth errors) or remove the stub file |
| P1-2 | `disabled_by_default` not verified | Audit which diagnostic/rarely-used entities should use `disabled_by_default=True` and apply where appropriate |
| P1-3 | No English README / docs | Add English README or dedicate a `docs/en/` section for Gold-level documentation |
| P1-4 | mypy not enforced in CI | Consider adding a `mypy` CI step (currently configured in `pyproject.toml` but not in `ci.yaml`) |

### P2 — Nice-to-Have

| # | Issue | Action |
|---|---|---|
| P2-1 | ruff format/import-order jobs are `continue-on-error: true` | Make these blocking once formatting is stable (all files currently pass) |
| P2-2 | pypdf not installed in CI | Install `pypdf` in test environment to enable PDF register mapping test |
| P2-3 | Coverage threshold | Verify `fail_under = 80` in `[tool.coverage.report]` is met; add coverage badge |
| P2-4 | English-language troubleshooting docs | For HACS discoverability, add an English troubleshooting section to README |
