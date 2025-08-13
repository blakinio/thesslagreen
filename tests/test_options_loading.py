import importlib
import logging
from pathlib import Path

import custom_components.thessla_green_modbus.const as const


def _restore_const(monkeypatch, original_read_text):
    monkeypatch.setattr(Path, "read_text", original_read_text)
    importlib.reload(const)


def test_missing_options_file(monkeypatch, caplog):
    original_read_text = Path.read_text

    def missing(_self):
        raise FileNotFoundError

    monkeypatch.setattr(Path, "read_text", missing)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        importlib.reload(const)

    assert const.SPECIAL_MODE_OPTIONS == []
    assert "special_modes.json" in caplog.text

    _restore_const(monkeypatch, original_read_text)


def test_malformed_options_file(monkeypatch, caplog):
    original_read_text = Path.read_text

    def malformed(_self):
        return "{"

    monkeypatch.setattr(Path, "read_text", malformed)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        importlib.reload(const)

    assert const.SPECIAL_MODE_OPTIONS == []
    assert "special_modes.json" in caplog.text

    _restore_const(monkeypatch, original_read_text)
