import logging
from pathlib import Path

import custom_components.thessla_green_modbus.const as const


def test_deep_scan_defaults():
    """Ensure deep scan option is defined and defaults to False."""
    assert const.CONF_DEEP_SCAN == "deep_scan"
    assert const.DEFAULT_DEEP_SCAN is False


def test_missing_options_file(monkeypatch, caplog):
    def missing(_self: Path) -> str:  # pragma: no cover - simple stub
        raise FileNotFoundError

    monkeypatch.setattr(Path, "read_text", missing)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        options = const._load_json_option("special_modes.json")

    assert options == []  # nosec B101
    assert "special_modes.json" in caplog.text  # nosec B101


def test_malformed_options_file(monkeypatch, caplog):
    def malformed(_self: Path) -> str:  # pragma: no cover - simple stub
        return "{"

    monkeypatch.setattr(Path, "read_text", malformed)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        options = const._load_json_option("special_modes.json")

    assert options == []  # nosec B101
    assert "special_modes.json" in caplog.text  # nosec B101
