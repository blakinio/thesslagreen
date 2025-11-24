import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.entity_mappings import (
    ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.registers.loader import (
    get_all_registers,
)
from custom_components.thessla_green_modbus.scanner_core import (
    DeviceCapabilities,
)


async def _setup_coordinator():
    """Create coordinator with forced full register list."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.bus = MagicMock()
    hass.bus.async_listen_once = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *a: func(*a))

    # Build scan result covering all registers
    scan_regs = {
        "input_registers": [],
        "holding_registers": [],
        "coil_registers": [],
        "discrete_inputs": [],
    }
    for reg in get_all_registers():
        if reg.function == 4:
            scan_regs["input_registers"].append(reg.name)
        elif reg.function == 3:
            scan_regs["holding_registers"].append(reg.name)
        elif reg.function == 1:
            scan_regs["coil_registers"].append(reg.name)
        elif reg.function == 2:
            scan_regs["discrete_inputs"].append(reg.name)

    scanner = AsyncMock()
    scanner.scan_device.return_value = {
        "available_registers": scan_regs,
        "capabilities": DeviceCapabilities(),
    }
    scanner.close = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner),
        ),
        patch.object(ThesslaGreenModbusCoordinator, "_test_connection", AsyncMock()),
    ):
        coordinator = ThesslaGreenModbusCoordinator(
            hass,
            host="host",
            port=502,
            slave_id=1,
            name="unit",
            force_full_register_list=True,
        )
        await coordinator.async_setup()
    return coordinator


def test_force_full_register_list():
    """All registers become entities or diagnostics when full list is forced."""

    async def run() -> None:
        coordinator = await _setup_coordinator()

        # All register names from definition file
        all_regs = {reg.name for reg in get_all_registers()}

        # Registers used by entity definitions
        entity_regs: set[str] = set()
        for mapping in ENTITY_MAPPINGS.values():
            entity_regs.update(mapping.keys())

        # Registers exposed via diagnostics (coordinator.available_registers)
        diag_regs = set().union(*coordinator.available_registers.values())

        # Full register list should be loaded
        assert diag_regs == all_regs

        # Every register is either represented by an entity or available for diagnostics
        missing = all_regs - (entity_regs | diag_regs)
        assert not missing

    asyncio.run(run())
