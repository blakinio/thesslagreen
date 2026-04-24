"""Read facade mixin for scanner core delegating to scanner.io helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pymodbus.client import AsyncModbusTcpClient

from . import io as scanner_domain_io

if TYPE_CHECKING:  # pragma: no cover - typing helper only
    from pymodbus.client import AsyncModbusSerialClient as AsyncModbusSerialClientType
else:
    AsyncModbusSerialClientType = Any


class ScannerReadFacadeMixin:
    """Delegating read API used by the scanner core class."""

    def _unpack_read_args(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None,
    ) -> tuple[AsyncModbusTcpClient | AsyncModbusSerialClientType | None, int, int]:
        return scanner_domain_io.unpack_read_args(self, client_or_address, address_or_count, count)

    def _resolve_transport_and_client(
        self,
        client: AsyncModbusTcpClient | AsyncModbusSerialClientType | None,
    ) -> tuple[Any, Any]:
        return scanner_domain_io.resolve_transport_and_client(self, client)

    def _track_input_failure(self, count: int, address: int) -> None:
        scanner_domain_io.track_input_failure(self, count, address)

    def _track_holding_failure(self, count: int, address: int) -> None:
        scanner_domain_io.track_holding_failure(self, count, address)

    async def _read_input(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        return await scanner_domain_io.read_input(
            self,
            client_or_address,
            address_or_count,
            count,
            skip_cache=skip_cache,
        )

    async def _read_register_block(
        self,
        read_fn: Any,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        return await scanner_domain_io.read_register_block(
            self,
            read_fn,
            client_or_start,
            start_or_count,
            count,
        )

    async def _read_input_block(
        self,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        return await self._read_register_block(
            self._read_input, client_or_start, start_or_count, count
        )

    async def _read_holding_block(
        self,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        return await self._read_register_block(
            self._read_holding, client_or_start, start_or_count, count
        )

    async def _read_holding(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        return await scanner_domain_io.read_holding(
            self,
            client_or_address,
            address_or_count,
            count,
            skip_cache=skip_cache,
        )

    async def _read_bit_registers(
        self,
        method_name: str,
        failed_key: str,
        type_name: str,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        return await scanner_domain_io.read_bit_registers(
            self,
            method_name,
            failed_key,
            type_name,
            client_or_address,
            address_or_count,
            count,
        )

    async def _read_coil(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        return await scanner_domain_io.read_coil(self, client_or_address, address_or_count, count)

    async def _read_discrete(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        return await scanner_domain_io.read_discrete(
            self, client_or_address, address_or_count, count
        )
