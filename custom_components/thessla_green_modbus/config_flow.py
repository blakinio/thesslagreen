from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .device_scanner import ThesslaDeviceScanner

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("port", default=8899): int,
        vol.Optional("unit", default=1): int,
    }
)


class ThesslaGreenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        host = user_input["host"].strip()
        port = int(user_input["port"])
        unit = int(user_input.get("unit", 1))

        scanner = ThesslaDeviceScanner(host, port, unit)

        try:
            info, caps, blocks = await scanner.scan()
        except Exception as e:
            _LOGGER.error("Unexpected error while validating input for %s:%s: %s", host, port, e)
            errors["base"] = "cannot_connect"
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        # PREZENTACJA: używaj asdict – nie iteruj po .items() obiektu dataclass
        caps_dict = asdict(caps)
        enabled_caps = [k for k, v in caps_dict.items() if bool(v)]
        title = f"ThesslaGreen @ {host}:{port}"
        desc = (
            f"Model: {info.model}, FW: {info.firmware}. "
            f"Bloki: {len(blocks)}. Aktywne możliwości: {', '.join(enabled_caps) if enabled_caps else 'brak'}."
        )

        # Unikalność config_entry po host:port
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=title, data={"host": host, "port": port, "unit": unit}, description=desc)
