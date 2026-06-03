"""Direct unit tests for _config_flow/reauth.py::process_reauth_submission."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus._config_flow.reauth import process_reauth_submission
from custom_components.thessla_green_modbus.const import (
    CONF_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    MAX_BATCH_REGISTERS,
)
from custom_components.thessla_green_modbus.errors import CannotConnect, InvalidAuth
from pymodbus.exceptions import ConnectionException, ModbusException


def _logger() -> MagicMock:
    log = MagicMock()
    log.error = MagicMock()
    log.exception = MagicMock()
    return log


def _hass() -> SimpleNamespace:
    return SimpleNamespace()


def _valid_input(**overrides):
    base = {
        "host": "192.168.1.1",
        "port": 502,
        "slave_id": 1,
        CONF_MAX_REGISTERS_PER_REQUEST: DEFAULT_MAX_REGISTERS_PER_REQUEST,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_success_returns_info_and_empty_errors() -> None:
    expected = {"title": "ok"}
    validate = AsyncMock(return_value=expected)
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info == expected
    assert errors == {}


@pytest.mark.asyncio
async def test_cannot_connect_with_arg_sets_base_error() -> None:
    validate = AsyncMock(side_effect=CannotConnect("cannot_connect"))
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info is None
    assert errors["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_cannot_connect_without_arg_uses_default() -> None:
    validate = AsyncMock(side_effect=CannotConnect())
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info is None
    assert errors["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_invalid_auth_sets_base_error() -> None:
    validate = AsyncMock(side_effect=InvalidAuth)
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info is None
    assert errors["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_max_registers_below_range_raises_vol_invalid() -> None:
    info, errors = await process_reauth_submission(
        _valid_input(**{CONF_MAX_REGISTERS_PER_REQUEST: 0}),
        validate_input=AsyncMock(),
        hass=_hass(),
        logger=_logger(),
    )
    assert info is None
    assert CONF_MAX_REGISTERS_PER_REQUEST in errors


@pytest.mark.asyncio
async def test_max_registers_above_range_raises_vol_invalid() -> None:
    info, errors = await process_reauth_submission(
        _valid_input(**{CONF_MAX_REGISTERS_PER_REQUEST: MAX_BATCH_REGISTERS + 1}),
        validate_input=AsyncMock(),
        hass=_hass(),
        logger=_logger(),
    )
    assert info is None
    assert CONF_MAX_REGISTERS_PER_REQUEST in errors


@pytest.mark.asyncio
async def test_max_registers_at_boundary_passes() -> None:
    validate = AsyncMock(return_value={"title": "ok"})
    info, errors = await process_reauth_submission(
        _valid_input(**{CONF_MAX_REGISTERS_PER_REQUEST: MAX_BATCH_REGISTERS}),
        validate_input=validate,
        hass=_hass(),
        logger=_logger(),
    )
    assert info is not None
    assert errors == {}


@pytest.mark.asyncio
async def test_connection_exception_sets_cannot_connect() -> None:
    validate = AsyncMock(side_effect=ConnectionException("refused"))
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info is None
    assert errors["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_modbus_exception_sets_cannot_connect() -> None:
    validate = AsyncMock(side_effect=ModbusException("framing"))
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info is None
    assert errors["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_value_error_sets_invalid_input() -> None:
    validate = AsyncMock(side_effect=ValueError("bad int"))
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info is None
    assert errors["base"] == "invalid_input"


@pytest.mark.asyncio
async def test_key_error_sets_invalid_input() -> None:
    validate = AsyncMock(side_effect=KeyError("missing_key"))
    info, errors = await process_reauth_submission(
        _valid_input(), validate_input=validate, hass=_hass(), logger=_logger()
    )
    assert info is None
    assert errors["base"] == "invalid_input"
