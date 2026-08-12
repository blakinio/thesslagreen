# mypy: ignore-errors
"""Exercise remaining scanner I/O core compatibility branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from custom_components.thessla_green_modbus.scanner import io_core


def test_ensure_pymodbus_client_module_attaches_client_and_sync_alias() -> None:
    pymodbus_mod = SimpleNamespace()
    async_client = object()
    client_mod = SimpleNamespace(AsyncModbusTcpClient=async_client)
    with patch.object(
        io_core.importlib, "import_module", side_effect=[pymodbus_mod, client_mod]
    ):
        io_core.ensure_pymodbus_client_module()
    assert pymodbus_mod.client is client_mod
    assert client_mod.ModbusTcpClient is async_client


def test_ensure_pymodbus_client_module_preserves_existing_aliases() -> None:
    existing_client = object()
    existing_sync = object()
    pymodbus_mod = SimpleNamespace(client=existing_client)
    client_mod = SimpleNamespace(AsyncModbusTcpClient=object(), ModbusTcpClient=existing_sync)
    with patch.object(
        io_core.importlib, "import_module", side_effect=[pymodbus_mod, client_mod]
    ):
        io_core.ensure_pymodbus_client_module()
    assert pymodbus_mod.client is existing_client
    assert client_mod.ModbusTcpClient is existing_sync


def test_ensure_pymodbus_client_module_import_failure_is_safe() -> None:
    with patch.object(io_core.importlib, "import_module", side_effect=ImportError("missing")):
        io_core.ensure_pymodbus_client_module()
