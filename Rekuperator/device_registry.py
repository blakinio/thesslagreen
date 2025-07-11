"""Device registry for TeslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def get_device_info(entry_id: str, host: str) -> DeviceInfo:
    """Get device info for TeslaGreen device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=f"TeslaGreen Rekuperator ({host})",
        manufacturer="TeslaGreen",
        model="Modbus Rekuperator",
        sw_version="1.0.0",
        configuration_url=f"http://{host}",
        hw_version="Rev. 1.0",
        suggested_area="Piwnica",
    )
