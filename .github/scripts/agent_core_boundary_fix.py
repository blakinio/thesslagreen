from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"{path}: expected {count} matches, found {actual}: {old!r}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")


# Core configuration model accepts plain mappings only.
replace(
    "custom_components/thessla_green_modbus/core/models.py",
    "from dataclasses import dataclass\nfrom datetime import timedelta\nfrom typing import TYPE_CHECKING, Any, cast\n\nif TYPE_CHECKING:\n    from homeassistant.config_entries import ConfigEntry\n",
    "from collections.abc import Mapping\nfrom dataclasses import dataclass\nfrom datetime import timedelta\nfrom typing import Any, cast\n",
)
replace(
    "custom_components/thessla_green_modbus/core/models.py",
    "    @classmethod\n    def from_entry(cls, entry: ConfigEntry | Any) -> CoordinatorConfig:\n"
    "        \"\"\"Build a CoordinatorConfig from a Home Assistant config entry.\"\"\"\n"
    "        data = entry.data\n"
    "        options = entry.options\n",
    "    @classmethod\n"
    "    def from_mappings(\n"
    "        cls, data: Mapping[str, Any], options: Mapping[str, Any]\n"
    "    ) -> CoordinatorConfig:\n"
    "        \"\"\"Build normalized device configuration from plain mappings.\"\"\"\n",
)

# DeviceClient has no Home Assistant objects in its constructor or state.
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "from contextlib import suppress\nfrom typing import TYPE_CHECKING, Any\n",
    "from typing import Any\n",
)
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "\nif TYPE_CHECKING:\n    from homeassistant.config_entries import ConfigEntry\n    from homeassistant.core import HomeAssistant\n",
    "",
)
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "        *,\n        hass: HomeAssistant,\n        effective_batch: int,\n",
    "        *,\n        effective_batch: int,\n",
)
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "        backoff: float,\n        backoff_jitter: float | tuple[float, float] | None,\n        entry: ConfigEntry | None = None,\n",
    "        backoff: float,\n        backoff_jitter: float | tuple[float, float] | None,\n",
)
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "        self.config = config\n        self.hass = hass\n",
    "        self.config = config\n",
)
replace(
    "custom_components/thessla_green_modbus/core/client.py",
    "        self.capabilities = DeviceCapabilities()\n"
    "        if entry is not None and isinstance(entry.data.get(\"capabilities\"), dict):\n"
    "            with suppress(TypeError, ValueError):\n"
    "                self.capabilities = DeviceCapabilities(**entry.data[\"capabilities\"])\n"
    "        self.device_info: dict[str, Any] = {}\n",
    "        self.capabilities = DeviceCapabilities()\n"
    "        self.device_info: dict[str, Any] = {}\n",
)

# HA adapter performs ConfigEntry -> plain mapping conversion and owns HA objects.
replace(
    "custom_components/thessla_green_modbus/_setup.py",
    "    config = CoordinatorConfig.from_entry(entry)\n",
    "    config = CoordinatorConfig.from_mappings(entry.data, entry.options)\n",
)
replace(
    "custom_components/thessla_green_modbus/coordinator/coordinator.py",
    "            normalized_cfg,\n            hass=hass,\n            effective_batch=_pre_effective_batch,\n",
    "            normalized_cfg,\n            effective_batch=_pre_effective_batch,\n",
)
replace(
    "custom_components/thessla_green_modbus/coordinator/coordinator.py",
    "            backoff=_pre_backoff,\n            backoff_jitter=_pre_jitter,\n            entry=entry,\n",
    "            backoff=_pre_backoff,\n            backoff_jitter=_pre_jitter,\n",
)

# Test factories no longer invent a Home Assistant object for a domain client.
replace(
    "tests/helpers_modbus.py",
    "from unittest.mock import MagicMock\n\n",
    "",
)
replace(
    "tests/helpers_modbus.py",
    "    The ``config`` and ``hass`` arguments default to values produced by\n"
    "    :func:`make_config` and a fresh ``MagicMock`` respectively.\n",
    "    The ``config`` argument defaults to a value produced by :func:`make_config`.\n",
)
replace(
    "tests/helpers_modbus.py",
    "    config = make_config()\n    hass = MagicMock()\n    return ThesslaGreenDeviceClient(\n"
    "        config,\n        hass=hass,\n",
    "    config = make_config()\n    return ThesslaGreenDeviceClient(\n        config,\n",
)

replace(
    "tests/test_device_client.py",
    "    config = _make_config()\n    hass = MagicMock()\n    return ThesslaGreenDeviceClient(\n"
    "        config,\n        hass=hass,\n",
    "    config = _make_config()\n    return ThesslaGreenDeviceClient(\n        config,\n",
)
replace(
    "tests/test_device_client.py",
    "    hass = MagicMock()\n    client = ThesslaGreenDeviceClient(\n"
    "        config,\n        hass=hass,\n",
    "    client = ThesslaGreenDeviceClient(\n        config,\n",
    count=3,
)
replace(
    "tests/test_integration.py",
    "    config = CoordinatorConfig.from_entry(entry)\n",
    "    config = CoordinatorConfig.from_mappings(entry.data, entry.options)\n",
)
replace(
    "tests/test_integration.py",
    "    \"\"\"CoordinatorConfig should parse connection and option fields from entry.\"\"\"\n",
    "    \"\"\"CoordinatorConfig should normalize plain entry data/options mappings.\"\"\"\n",
)

# Add a structural regression test for the HA-free domain layers.
test_path = ROOT / "tests/test_domain_layer_boundaries.py"
test_path.write_text(
    '''"""Architectural boundary tests for Home Assistant-free domain layers."""\n\nfrom __future__ import annotations\n\nimport ast\nfrom pathlib import Path\n\n\nCOMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "thessla_green_modbus"\nDOMAIN_DIRS = ("core", "transport", "registers", "scanner")\n\n\ndef test_domain_layers_do_not_import_homeassistant() -> None:\n    """Core transport/register/scanner modules must not import Home Assistant."""\n    violations: list[str] = []\n    for dirname in DOMAIN_DIRS:\n        for path in (COMPONENT / dirname).rglob("*.py"):\n            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))\n            for node in ast.walk(tree):\n                if isinstance(node, ast.Import):\n                    modules = [alias.name for alias in node.names]\n                elif isinstance(node, ast.ImportFrom):\n                    modules = [node.module or ""]\n                else:\n                    continue\n                for module in modules:\n                    if module == "homeassistant" or module.startswith("homeassistant."):\n                        violations.append(f"{path.relative_to(COMPONENT)} -> {module}")\n\n    assert not violations, "Home Assistant imports crossed domain boundary: " + "; ".join(violations)\n''',
    encoding="utf-8",
)

# Remove temporary automation scaffolding from the resulting tree.
for temporary in (
    ROOT / ".github/scripts/agent_core_boundary_fix.py",
    ROOT / ".github/workflows/agent-core-boundary-fix.yml",
):
    if temporary.exists():
        temporary.unlink()
