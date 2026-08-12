"""Exercise the runtime helper declarations on the shared Modbus IO mixin."""

from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.core.io_mixin import _ModbusIOMixin


@pytest.mark.asyncio
async def test_io_mixin_required_helper_declarations_are_runtime_safe() -> None:
    """Direct introspection of required helper declarations remains a no-op."""
    mixin = _ModbusIOMixin()

    assert await mixin._ensure_connection() is None
    assert mixin._find_register_name("holding_registers", 10) is None
    assert mixin._process_register_value("example", 1) is None
    assert mixin._clear_register_failure("example") is None
    assert mixin._mark_registers_failed(["example", None]) is None
