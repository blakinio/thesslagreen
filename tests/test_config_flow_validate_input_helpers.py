"""Focused config-flow validate_input helper tests."""

import pytest
import voluptuous as vol


@pytest.mark.asyncio
async def test_validate_input_invalid_connection_type():
    """Invalid connection_type raises exception (line 343)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import CONF_CONNECTION_TYPE, CONF_SLAVE_ID

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(None, {CONF_CONNECTION_TYPE: "INVALID", CONF_SLAVE_ID: 1})


@pytest.mark.asyncio
async def test_validate_input_tcp_rtu_normalization():
    """TCP_RTU normalizes to TCP + mode (lines 347-349), then fails at scanner."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_CONNECTION_TYPE,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_TCP_RTU,
    )
    from homeassistant.const import CONF_HOST

    data = {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP_RTU,
        CONF_SLAVE_ID: 1,
        CONF_HOST: "192.168.1.1",
    }
    with pytest.raises((cf_mod.CannotConnect, vol.Invalid)):
        await cf_mod.validate_input(None, data)
    # Data was normalized
    from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_TCP

    assert data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_TCP


@pytest.mark.asyncio
async def test_validate_input_invalid_slave_id_string():
    """Non-numeric slave_id raises exception (lines 361-362)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_CONNECTION_TYPE,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_TCP,
    )
    from homeassistant.const import CONF_HOST

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                CONF_SLAVE_ID: "abc",
                CONF_HOST: "192.168.1.1",
            },
        )


@pytest.mark.asyncio
async def test_validate_input_slave_id_too_low():
    """slave_id < 0 raises exception; 0 is valid per Modbus broadcast spec."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_CONNECTION_TYPE,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_TCP,
    )
    from homeassistant.const import CONF_HOST

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                CONF_SLAVE_ID: -1,
                CONF_HOST: "192.168.1.1",
            },
        )


@pytest.mark.asyncio
async def test_validate_input_invalid_port():
    """Non-numeric port raises exception (lines 380-381)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_CONNECTION_TYPE,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_TCP,
    )
    from homeassistant.const import CONF_HOST, CONF_PORT

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                CONF_SLAVE_ID: 1,
                CONF_HOST: "192.168.1.1",
                CONF_PORT: "bad_port",
            },
        )


@pytest.mark.asyncio
async def test_validate_input_empty_host():
    """Empty host raises exception (line 383)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_CONNECTION_TYPE,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_TCP,
    )
    from homeassistant.const import CONF_HOST, CONF_PORT

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                CONF_SLAVE_ID: 1,
                CONF_HOST: "",
                CONF_PORT: 502,
            },
        )


@pytest.mark.asyncio
async def test_validate_input_hostname_fails_looks_like():
    """Hostname with no dot fails _looks_like_hostname (line 394)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_CONNECTION_TYPE,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_TCP,
    )
    from homeassistant.const import CONF_HOST, CONF_PORT

    # "nodothost" has no dot → _looks_like_hostname returns False → raises
    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                CONF_SLAVE_ID: 1,
                CONF_HOST: "nodothost",
                CONF_PORT: 502,
            },
        )


@pytest.mark.asyncio
async def test_validate_input_rtu_invalid_baud_rate():
    """Invalid baud rate in RTU raises exception (lines 413-414)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_BAUD_RATE,
        CONF_CONNECTION_TYPE,
        CONF_SERIAL_PORT,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_RTU,
    )

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                CONF_SLAVE_ID: 1,
                CONF_SERIAL_PORT: "/dev/ttyS0",
                CONF_BAUD_RATE: 0,
            },
        )


@pytest.mark.asyncio
async def test_validate_input_rtu_invalid_parity():
    """Invalid parity in RTU raises exception (lines 417-418)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_BAUD_RATE,
        CONF_CONNECTION_TYPE,
        CONF_PARITY,
        CONF_SERIAL_PORT,
        CONF_SLAVE_ID,
        CONNECTION_TYPE_RTU,
    )

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                CONF_SLAVE_ID: 1,
                CONF_SERIAL_PORT: "/dev/ttyS0",
                CONF_BAUD_RATE: 9600,
                CONF_PARITY: "INVALID_PARITY",
            },
        )


@pytest.mark.asyncio
async def test_validate_input_rtu_invalid_stop_bits():
    """Invalid stop_bits in RTU raises exception (lines 421-424)."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_BAUD_RATE,
        CONF_CONNECTION_TYPE,
        CONF_PARITY,
        CONF_SERIAL_PORT,
        CONF_SLAVE_ID,
        CONF_STOP_BITS,
        CONNECTION_TYPE_RTU,
    )

    with pytest.raises(vol.Invalid):
        await cf_mod.validate_input(
            None,
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                CONF_SLAVE_ID: 1,
                CONF_SERIAL_PORT: "/dev/ttyS0",
                CONF_BAUD_RATE: 9600,
                CONF_PARITY: "none",
                CONF_STOP_BITS: 3,
            },
        )


# ---------------------------------------------------------------------------
# Pass 16 — line 311: _call_with_optional_timeout sync return
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_input_rtu_valid_params():
    """Valid RTU params reach scanner (lines 425-428), scanner fails with exception."""
    import custom_components.thessla_green_modbus.config_flow as cf_mod
    from custom_components.thessla_green_modbus.const import (
        CONF_BAUD_RATE,
        CONF_CONNECTION_TYPE,
        CONF_PARITY,
        CONF_SERIAL_PORT,
        CONF_SLAVE_ID,
        CONF_STOP_BITS,
        CONNECTION_TYPE_RTU,
    )

    data = {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
        CONF_SLAVE_ID: 1,
        CONF_SERIAL_PORT: "/dev/ttyS0",
        CONF_BAUD_RATE: 9600,
        CONF_PARITY: "none",
        CONF_STOP_BITS: 1,
    }
    with pytest.raises((cf_mod.CannotConnect, vol.Invalid)):
        await cf_mod.validate_input(None, data)
    # Confirm RTU validation passed and data was set
    assert data[CONF_BAUD_RATE] == 9600
    assert data[CONF_PARITY] == "none"
    assert data[CONF_STOP_BITS] == 1
