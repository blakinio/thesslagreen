"""Guard: every schedule register name used by services exists in registry."""

from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.registers.loader import get_register_definition

_SEASONS = ("summer", "winter")
_DOW = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_SLOTS = (1, 2, 3, 4)


@pytest.mark.parametrize("season", _SEASONS)
@pytest.mark.parametrize("dow", _DOW)
@pytest.mark.parametrize("slot", _SLOTS)
def test_schedule_register_exists(season: str, dow: str, slot: int) -> None:
    name = f"schedule_{season}_{dow}_{slot}"
    definition = get_register_definition(name)
    assert definition is not None, f"Service writes to nonexistent register {name!r}"
    assert definition.function == 3


@pytest.mark.parametrize("season", _SEASONS)
@pytest.mark.parametrize("dow", _DOW)
@pytest.mark.parametrize("slot", _SLOTS)
def test_setting_register_exists(season: str, dow: str, slot: int) -> None:
    name = f"setting_{season}_{dow}_{slot}"
    definition = get_register_definition(name)
    assert definition is not None, f"Service writes to nonexistent register {name!r}"
    assert definition.function == 3
