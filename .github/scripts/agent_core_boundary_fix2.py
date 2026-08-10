from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "tests/test_device_client.py"
text = path.read_text(encoding="utf-8")
old = '''def test_device_client_hass_stored():
    hass = MagicMock()
    config = _make_config()
    client = ThesslaGreenDeviceClient(
        config,
        hass=hass,
        effective_batch=100,
        resolved_connection_mode=None,
        backoff=0.5,
        backoff_jitter=None,
    )
    assert client.hass is hass
'''
new = '''def test_device_client_does_not_store_home_assistant_object():
    client = _make_client()
    assert not hasattr(client, "hass")
'''
if text.count(old) != 1:
    raise RuntimeError("expected legacy DeviceClient hass-storage test exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
Path(__file__).unlink()
