"""Tests for ThesslaGreenModbusCoordinator."""

import pytest

pytest.skip("Requires Home Assistant environment", allow_module_level=True)

# The import below reflects the new coordinator name used by the integration.
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)

