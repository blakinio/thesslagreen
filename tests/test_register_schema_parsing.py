"""Unit tests covering register schema parsing and validation."""

from __future__ import annotations

import pytest

from custom_components.thessla_green_modbus.registers.schema import (
    RegisterDefinition,
)


def test_register_definition_normalises_fields() -> None:
    """String inputs are normalised to canonical types and values."""

    definition = RegisterDefinition(
        function="input_registers",
        address_dec="16",
        name="test_register",
        access="R",
        description="desc",
        description_en="desc",
    )

    assert definition.function == 4  # nosec: intended assertion
    assert definition.address_dec == 16  # nosec: intended assertion


def test_register_definition_rejects_mismatched_lengths() -> None:
    """Length must match the implied type size."""

    with pytest.raises(ValueError):
        RegisterDefinition(
            function=3,
            address_dec=1,
            name="invalid_length",
            access="RW",
            description="desc",
            description_en="desc",
            type="u32",
            length=1,
        )


def test_register_definition_rejects_hex_address() -> None:
    """Hexadecimal address strings are rejected."""

    with pytest.raises(ValueError):
        RegisterDefinition(
            function=1,
            address_dec="0x10",
            name="mismatched",
            access="R",
            description="desc",
            description_en="desc",
        )
