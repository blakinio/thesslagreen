# Contributing to ThesslaGreen Modbus

Thank you for contributing to the ThesslaGreen AirPack integration for Home Assistant.

## Development baseline

- Python **3.13+** for the declared minimum Home Assistant line.
- Home Assistant **2026.1.0+**.
- `main` is the only long-lived branch. Create task branches from `main`; do not reintroduce `dev`/`develop`.
- Register addresses in code/documentation use decimal notation.
- The canonical register specification is `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`.

Clone the repository with:

```bash
git clone https://github.com/blakinio/thesslagreen.git
cd thesslagreen
```

Create and activate a virtual environment, then install the development stack:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
pre-commit install
```

## Required local checks

Run the relevant focused tests while developing. Before opening a PR, run as much of the canonical gate as your environment supports:

```bash
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
python -m compileall -q custom_components/thessla_green_modbus tests tools
mypy custom_components/thessla_green_modbus
python tools/compare_registers_with_reference.py --show-renames
python tools/compare_airpack4_vendor_coverage.py
python tools/check_translations.py
python tools/check_maintainability.py
python tools/validate_entity_mappings.py
pytest tests/ -q
```

GitHub CI is authoritative for the complete environment. It additionally validates Hassfest, HACS, the declared minimum Home Assistant API contract, a current stable Home Assistant contract, and supported pymodbus boundary versions.

## Architecture guardrails

Keep these repository invariants unless an approved architectural decision explicitly changes them:

- no legacy modules;
- no compatibility/re-export/proxy shims;
- `core/`, `transport/`, `registers/`, and `scanner/` must not gain Home Assistant runtime imports;
- Home Assistant entities/actions must not perform raw Modbus I/O directly;
- Modbus requests must respect the integration's maximum 16-register safety boundary;
- the coordinator owns Home Assistant scheduling/state publication, while device/transport behavior belongs below that boundary;
- destructive, service-only, communication, and other risk-marked controls must remain opt-in/guarded;
- a failed final Modbus write must never be reported as a successful Home Assistant action.

Before attempting broad read-path/mixin consolidation, read [`docs/core_consolidation_plan.md`](docs/core_consolidation_plan.md). That work is deliberately gated by longer real-device validation.

## Home Assistant behavior

Use Home Assistant-native patterns:

- asynchronous I/O only;
- config entries/config flow rather than YAML configuration;
- stable config-entry and entity unique IDs;
- translated `ServiceValidationError`/`HomeAssistantError` semantics at the HA boundary;
- integration-wide actions registered from process-level `async_setup()`;
- diagnostics with privacy-conscious redaction;
- Repairs for actionable persistent failures where appropriate.

Do not weaken CI, disable failing tests, add blanket ignores, or convert real failures into logs-only success paths.

## Modbus and security

Modbus TCP/raw RTU-over-TCP should be treated as trusted-LAN protocols. Do not document or recommend public Internet exposure or direct port-forwarding. Prefer VLAN/firewall isolation and authenticated remote access such as a VPN. See [`SECURITY.md`](SECURITY.md).

For RTU/USB production examples use persistent paths such as `/dev/serial/by-id/...` rather than `/dev/ttyUSB0`.

## Register changes

When changing register definitions:

1. edit the canonical JSON source;
2. keep register names/addresses and multi-register semantics compatible unless a migration is explicitly designed;
3. validate vendor coverage and entity mappings;
4. add tests for encoding/decoding, batching boundaries, unsupported-register behavior, and safe write/read-back where relevant.

Never infer that a register is globally unsupported because one AirPack/firmware returns Illegal Data Address.

## Testing on real hardware

Hardware evidence is a separate evidence class from CI. Record the exact candidate commit/version, Home Assistant version, AirPack model/firmware, transport, slave ID, polling interval, and batch size.

For runtime-sensitive changes, follow [`docs/real_device_validation.md`](docs/real_device_validation.md), including representative writes, reconnect behavior, diagnostic scan restoration, and soak testing. Do not turn historical device evidence into a claim about a newer candidate.

## Pull requests

Use Conventional Commit-style titles where practical (`fix:`, `feat:`, `docs:`, `test:`, `refactor:`, `chore:`). PR descriptions should state:

- what changed and why;
- compatibility or safety impact;
- validation performed and its exact result;
- any physical-device evidence or explicitly pending hardware gates;
- rollback considerations for high-risk changes.

For large/multi-step tasks, follow the repository checkpoint/handoff rules in `AGENTS.md` and `docs/agents/CONTEXT_HANDOFF.md`.

## Releases

Do not tag or publish from an unverified branch. Follow [`docs/release_process.md`](docs/release_process.md). `manifest.json` and `pyproject.toml` versions must match, CI must be green, and hardware-validation claims in release notes must match actual recorded evidence.
