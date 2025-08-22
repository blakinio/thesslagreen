"""Smoke test for example Home Assistant configuration."""

from pathlib import Path


def test_example_configuration_loads():
    """Ensure the example configuration file contains expected sections."""
    path = Path(__file__).resolve().parent.parent / "example_configuration.yaml"
    text = path.read_text(encoding="utf-8")
    assert "template:" in text
    assert "automation:" in text
