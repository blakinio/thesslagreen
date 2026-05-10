"""Tests for ThesslaGreenModbusCoordinator._parse_backoff_jitter."""

from custom_components.thessla_green_modbus.const import DEFAULT_BACKOFF_JITTER
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)


class TestParseBackoffJitter:
    """Direct tests for the _parse_backoff_jitter parser."""

    def test_numeric_inputs(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(0) == 0.0
        assert parse(0.0) == 0.0
        assert parse(1) == 1.0
        assert parse(1.5) == 1.5

    def test_string_inputs(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse("1.5") == 1.5
        assert parse("0") == 0.0
        assert parse("not-a-number") is None
        assert parse("") is None

    def test_tuple_list_inputs(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse((1.0, 2.0)) == (1.0, 2.0)
        assert parse([1, 2]) == (1.0, 2.0)
        assert parse((1.0, 2.0, 3.0)) == (1.0, 2.0)

    def test_invalid_sequence_returns_none(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(["a", "b"]) is None
        assert parse((None, None)) is None

    def test_none_and_sentinel_defaults(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(None) is None
        assert parse({"key": "value"}) == DEFAULT_BACKOFF_JITTER  # type: ignore[arg-type]
