from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    text = read(path)
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"{path}: expected {count} matches, found {actual}: {old!r}")
    write(path, text.replace(old, new, count))


def sub(path: str, pattern: str, repl: str, *, count: int = 1, flags: int = 0) -> None:
    text = read(path)
    updated, actual = re.subn(pattern, repl, text, count=count, flags=flags)
    if actual != count:
        raise RuntimeError(f"{path}: expected {count} regex matches, found {actual}: {pattern!r}")
    write(path, updated)


# unique_id_migration.py: do not reuse a str loop variable for an Optional lookup result.
replace(
    "custom_components/thessla_green_modbus/unique_id_migration.py",
    "    for key, (reg_name, reg_type, bit) in lookup.items():\n"
    "        register_to_key.setdefault(reg_name, key)\n",
    "    for entity_key, (reg_name, reg_type, bit) in lookup.items():\n"
    "        register_to_key.setdefault(reg_name, entity_key)\n",
)
replace(
    "custom_components/thessla_green_modbus/unique_id_migration.py",
    "            reverse_by_address.setdefault((address, bit_idx), key)\n",
    "            reverse_by_address.setdefault((address, bit_idx), entity_key)\n",
)
replace(
    "custom_components/thessla_green_modbus/unique_id_migration.py",
    "        key = reverse_by_address.get((address, bit_idx)) or reverse_by_address.get((address, None))\n"
    "        if key:\n"
    "            bit_suffix = f\"_bit{bit_idx}\" if bit_idx is not None else \"\"\n"
    "            return f\"{slave_id}_{key}_{address}{bit_suffix}\"\n",
    "        resolved_key = reverse_by_address.get((address, bit_idx)) or reverse_by_address.get(\n"
    "            (address, None)\n"
    "        )\n"
    "        if resolved_key:\n"
    "            bit_suffix = f\"_bit{bit_idx}\" if bit_idx is not None else \"\"\n"
    "            return f\"{slave_id}_{resolved_key}_{address}{bit_suffix}\"\n",
)

# capabilities_mixin.py: declare the mixin host contract and normalize packed register values.
replace(
    "custom_components/thessla_green_modbus/core/capabilities_mixin.py",
    "    device_info: dict[str, Any]\n",
    "    device_info: dict[str, Any]\n    device_client: Any\n",
)
replace(
    "custom_components/thessla_green_modbus/core/capabilities_mixin.py",
    "        yy = _bcd((raw_yymm >> 8) & 0xFF)\n"
    "        mm = _bcd(raw_yymm & 0xFF)\n"
    "        dd = _bcd((raw_ddtt >> 8) & 0xFF)\n"
    "        hh = _bcd((raw_ggmm >> 8) & 0xFF)\n"
    "        mi = _bcd(raw_ggmm & 0xFF)\n"
    "        ss = _bcd((raw_sscc >> 8) & 0xFF)\n",
    "        yymm = int(raw_yymm)\n"
    "        ddtt = int(raw_ddtt)\n"
    "        ggmm = int(raw_ggmm)\n"
    "        sscc = int(raw_sscc)\n"
    "        yy = _bcd((yymm >> 8) & 0xFF)\n"
    "        mm = _bcd(yymm & 0xFF)\n"
    "        dd = _bcd((ddtt >> 8) & 0xFF)\n"
    "        hh = _bcd((ggmm >> 8) & 0xFF)\n"
    "        mi = _bcd(ggmm & 0xFF)\n"
    "        ss = _bcd((sscc >> 8) & 0xFF)\n",
)

# dispatch.py / schema.py: complete public helper signatures.
replace(
    "custom_components/thessla_green_modbus/services/dispatch.py",
    "import asyncio\nfrom typing import Any\n",
    "import asyncio\nfrom collections.abc import Iterator\nfrom typing import Any\n",
)
replace(
    "custom_components/thessla_green_modbus/services/dispatch.py",
    "def _iter_executable_steps(\n    steps: list[tuple[str, object, bool, str]],\n):\n",
    "def _iter_executable_steps(\n"
    "    steps: list[tuple[str, object, bool, str]],\n"
    ") -> Iterator[tuple[str, object, bool, str]]:\n",
)
replace(
    "custom_components/thessla_green_modbus/services/schema.py",
    "def _target_schema(fields: dict[Any, Any] | None = None):\n",
    "def _target_schema(fields: dict[Any, Any] | None = None) -> vol.Schema:\n",
)

# Config-flow validation: keep unknown BaseException passthrough explicit and typed.
replace(
    "custom_components/thessla_green_modbus/_config_flow/device_validation.py",
    "from typing import Any\n",
    "from typing import Any, NoReturn, cast\n",
)
replace(
    "custom_components/thessla_green_modbus/_config_flow/device_validation.py",
    "    return verify_cb\n",
    "    return cast(Callable[[], Any], verify_cb)\n",
)
replace(
    "custom_components/thessla_green_modbus/_config_flow/device_validation.py",
    ") -> Exception:\n    \"\"\"Map low-level exceptions to flow-facing exceptions.\"\"\"\n",
    ") -> BaseException:\n    \"\"\"Map low-level exceptions to flow-facing exceptions.\"\"\"\n",
)
replace(
    "custom_components/thessla_green_modbus/_config_flow/device_validation.py",
    "def _raise_if_unmapped(mapped: Exception, original: BaseException) -> None:\n",
    "def _raise_if_unmapped(mapped: BaseException, original: BaseException) -> NoReturn:\n",
)

# Retry typing: pymodbus exception classes are skipped imports, so preserve Exception explicitly.
replace(
    "custom_components/thessla_green_modbus/core/retry.py",
    "from typing import Any\n",
    "from typing import Any, cast\n",
)
replace(
    "custom_components/thessla_green_modbus/core/retry.py",
    "        return exc\n\n    log_coordinator_retry(\n",
    "        return cast(Exception, exc)\n\n    log_coordinator_retry(\n",
)

# Service handlers: declare dynamic coordinator use explicitly instead of mis-typing as object.
replace(
    "custom_components/thessla_green_modbus/services/handlers_schedule.py",
    "from __future__ import annotations\n\nfrom homeassistant.core",
    "from __future__ import annotations\n\nfrom typing import Any\n\nfrom homeassistant.core",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_schedule.py",
    "    coordinator: object, setting_register: str, temperature: float | None\n",
    "    coordinator: Any, setting_register: str, temperature: float | None\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_mode.py",
    "from __future__ import annotations\n\nfrom homeassistant.core",
    "from __future__ import annotations\n\nfrom typing import Any\n\nfrom homeassistant.core",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_mode.py",
    "    coordinator: object, deps: ServiceHandlerDeps, mode: str, entity_id: str\n",
    "    coordinator: Any, deps: ServiceHandlerDeps, mode: str, entity_id: str\n",
)

# Maintenance handlers: fully type the injected service-handler contracts.
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "from collections.abc import Awaitable, Callable\n",
    "from collections.abc import Awaitable, Callable, Iterator\nfrom typing import Any\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "ServiceAction = Callable[[str, object], Awaitable[bool]]\n",
    "type ServiceAction = Callable[[str, Any], Awaitable[bool]]\n"
    "type ServiceHandler = Callable[[ServiceCall], Awaitable[None]]\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "def _maintenance_registrations():\n",
    "def _maintenance_registrations() -> list[tuple[str, Any]]:\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "def _iter_maintenance_service_bindings(handlers: dict[str, object]):\n",
    "def _iter_maintenance_service_bindings(\n"
    "    handlers: dict[str, ServiceHandler],\n"
    ") -> Iterator[tuple[str, Any, ServiceHandler]]:\n",
)
sub(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    r"def _maintenance_handlers\(\n(?P<body>(?:    .*\n)+?)\) -> dict\[str, object\]:",
    lambda m: "def _maintenance_handlers(\n"
    + m.group("body").replace(": object,", ": ServiceHandler,")
    + ") -> dict[str, ServiceHandler]:",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "    schema: object,\n    handler: object,\n",
    "    schema: Any,\n    handler: ServiceHandler,\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "    hass: HomeAssistant, deps: ServiceHandlerDeps, handlers: dict[str, object]\n",
    "    hass: HomeAssistant, deps: ServiceHandlerDeps, handlers: dict[str, ServiceHandler]\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "    coordinator: object,\n    deps: ServiceHandlerDeps,\n",
    "    coordinator: Any,\n    deps: ServiceHandlerDeps,\n",
    count=1,
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_maintenance.py",
    "    coordinator: object,\n    entity_id: str,\n",
    "    coordinator: Any,\n    entity_id: str,\n",
    count=1,
)
# Inner target callbacks all use the real coordinator interface.
text = read("custom_components/thessla_green_modbus/services/handlers_maintenance.py")
text = text.replace("coordinator: object", "coordinator: Any")
# Builder functions all return a Home Assistant service handler.
text, changed = re.subn(
    r"(def _build_[a-z_]+_handler\(hass: HomeAssistant, deps: ServiceHandlerDeps\)):",
    r"\1 -> ServiceHandler:",
    text,
)
if changed != 7:
    raise RuntimeError(f"handlers_maintenance.py: expected 7 builder signatures, found {changed}")
text = text.replace("            opts = {}\n", "            opts: dict[str, Any] = {}\n")
write("custom_components/thessla_green_modbus/services/handlers_maintenance.py", text)

# Avoid cross-loop inferred container type conflicts.
replace(
    "custom_components/thessla_green_modbus/services/handlers_data.py",
    "            for rt, names in missing_sorted.items():\n                if names:\n",
    "            for rt, sorted_names in missing_sorted.items():\n                if sorted_names:\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_data.py",
    "                        names,\n                    )\n            for rt, names in indeterminate_sorted.items():\n                if names:\n",
    "                        sorted_names,\n                    )\n            for rt, sorted_names in indeterminate_sorted.items():\n                if sorted_names:\n",
)
replace(
    "custom_components/thessla_green_modbus/services/handlers_data.py",
    "                        names,\n                    )\n        return results\n",
    "                        sorted_names,\n                    )\n        return results\n",
)

# Coordinator/read mixins: describe attributes supplied by the composed host class.
replace(
    "custom_components/thessla_green_modbus/coordinator/schedule.py",
    "    _transport: BaseModbusTransport | None\n",
    "    _device_client: Any\n"
    "    data: dict[str, Any] | None\n"
    "    _transport: BaseModbusTransport | None\n",
)
replace(
    "custom_components/thessla_green_modbus/coordinator/schedule.py",
    "    async def _ensure_connection(self) -> None: ...\n",
    "    async def _ensure_connection(self) -> None: ...\n"
    "    def async_set_updated_data(self, data: dict[str, Any]) -> None: ...\n",
)
replace(
    "custom_components/thessla_green_modbus/core/io_mixin.py",
    "    _transport: BaseModbusTransport | None\n",
    "    device_client: Any\n    _transport: BaseModbusTransport | None\n",
)
replace(
    "custom_components/thessla_green_modbus/core/client_connection.py",
    "    offline_state: bool\n    statistics: dict[str, Any]\n",
    "    offline_state: bool\n"
    "    statistics: dict[str, Any]\n"
    "    retry: int\n"
    "    backoff: float\n"
    "    timeout: float\n",
)

# Scanner state/core type contracts.
replace(
    "custom_components/thessla_green_modbus/scanner/state.py",
    "    connection_mode: str\n",
    "    connection_mode: str | None\n",
    count=1,
)
replace(
    "custom_components/thessla_green_modbus/scanner/state.py",
    "    connection_mode: str,\n",
    "    connection_mode: str | None,\n",
    count=1,
)
replace(
    "custom_components/thessla_green_modbus/scanner/state.py",
    ") -> tuple[str, str, str | None]:\n",
    ") -> tuple[str, str | None, str | None]:\n",
)
replace(
    "custom_components/thessla_green_modbus/scanner/state.py",
    "    scanner: Any, *, known_missing_registers: dict[str, dict[str, Any]]\n",
    "    scanner: Any, *, known_missing_registers: dict[str, set[str]]\n",
)
replace(
    "custom_components/thessla_green_modbus/scanner/core.py",
    "    _sensor_unavailable_checks: dict[str, Any]\n",
    "    _sensor_unavailable_checks: dict[str, Any]\n"
    "    _known_missing_registers: dict[str, set[str]]\n"
    "    _input_register_map: dict[str, int]\n"
    "    _holding_register_map: dict[str, int]\n"
    "    _coil_register_map: dict[str, int]\n"
    "    _discrete_input_register_map: dict[str, int]\n"
    "    _multi_register_sizes: dict[str, int]\n",
)

# Small Any-return cleanups.
replace(
    "custom_components/thessla_green_modbus/coordinator/diagnostics.py",
    "        return firmware\n",
    "        return str(firmware)\n",
)
replace(
    "custom_components/thessla_green_modbus/diagnostics.py",
    "        return await translation.async_get_translations(\n"
    "            hass, hass.config.language, f\"component.{DOMAIN}\"\n"
    "        )\n",
    "        raw = await translation.async_get_translations(\n"
    "            hass, hass.config.language, f\"component.{DOMAIN}\"\n"
    "        )\n"
    "        return {str(key): str(value) for key, value in raw.items()}\n",
)
replace(
    "custom_components/thessla_green_modbus/select.py",
    "        self._states = definition[\"states\"]\n"
    "        self._reverse_states = {v: k for k, v in self._states.items()}\n",
    "        self._states: dict[str, Any] = dict(definition[\"states\"])\n"
    "        self._reverse_states: dict[Any, str] = {v: k for k, v in self._states.items()}\n",
)
replace(
    "custom_components/thessla_green_modbus/climate.py",
    "        if pending is not None:\n            return pending\n        return self._confirmed_fan_mode()\n",
    "        if pending is not None:\n            return str(pending)\n        return self._confirmed_fan_mode()\n",
)
replace(
    "custom_components/thessla_green_modbus/climate.py",
    "        if pending is not None:\n            return pending\n        return self._confirmed_preset_mode()\n",
    "        if pending is not None:\n            return str(pending)\n        return self._confirmed_preset_mode()\n",
)

# client.py: get() already has the declared dict[str, int] type; the cast is redundant.
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "from typing import TYPE_CHECKING, Any, cast\n",
    "from typing import TYPE_CHECKING, Any\n",
)
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "        return cast(dict[str, int], self._register_maps.get(register_type, {}))\n",
    "        return self._register_maps.get(register_type, {})\n",
)

# Remove this temporary workflow/script from the resulting commit.
for temporary in (
    ROOT / ".github/scripts/agent_mypy_fix.py",
    ROOT / ".github/workflows/agent-mypy-fix.yml",
):
    if temporary.exists():
        temporary.unlink()
