"""Tests for full scan phase helpers."""

from __future__ import annotations

from custom_components.thessla_green_modbus.scanner.full_scan_phase import (
    apply_word_register_block,
)


class _DummyScanner:
    def __init__(self) -> None:
        self.available_registers = {"input_registers": set(), "holding_registers": set()}
        self.failed_addresses = {
            "invalid_values": {"input_registers": set(), "holding_registers": set()}
        }
        self._registers = {4: {0: "reg_ok", 1: "reg_bad"}, 3: {}}
        self.invalid_logged: list[tuple[str, int]] = []

    def _is_valid_register_value(self, reg_name: str, value: int) -> bool:
        return reg_name != "reg_bad" and value < 100

    def _alias_names(self, function: int, address: int) -> set[str]:
        if function == 4 and address == 0:
            return {"reg_ok", "reg_ok_alias"}
        return set()

    def _log_invalid_value(self, reg_name: str, value: int) -> None:
        self.invalid_logged.append((reg_name, value))


def test_apply_word_register_block_normalizes_alias_invalid_and_unknown() -> None:
    scanner = _DummyScanner()
    unknown_registers = {"input_registers": {}, "holding_registers": {}}

    apply_word_register_block(
        scanner,
        function=4,
        register_group="input_registers",
        start=0,
        count=3,
        data=[10, 200],
        unknown_registers=unknown_registers,
    )

    assert scanner.available_registers["input_registers"] == {"reg_ok", "reg_ok_alias"}
    assert unknown_registers["input_registers"][1] == 200
    assert unknown_registers["input_registers"][2] == 12
    assert scanner.failed_addresses["invalid_values"]["input_registers"] == {1}
    assert scanner.invalid_logged == [("reg_bad", 200)]
