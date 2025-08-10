from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .device_scanner import ThesslaDeviceScanner  # alias zapewnia kompatybilność

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("port", default=8899): int,
        # wspieramy oba pola; w UI pokazuj "unit", ale obsłuż też legacy "slave_id"
        vol.Optional("unit", default=1): int,
        vol.Optional("slave_id"): int,
    }
)

async def validate_input(hass, data: Dict[str, Any]) -> Dict[str, Any]:
    host = data["host"].strip()
    port = int(data.get("port", 8899))
    unit = int(data.get("unit", data.get("slave_id", 1)))

    scanner = ThesslaDeviceScanner(host=host, port=port, unit=unit)  # nie przekazujemy retry/slave_id
    info, caps, blocks = await scanner.scan()

    return {
        "title": f"ThesslaGreen @ {host}:{port}",
        "host": host,
        "port": port,
        "unit": unit,
        "info": {"model": info.model, "firmware": info.firmware},
        "caps": asdict(caps),
        "blocks": {k: [hex(v[0]), hex(v[1])] for k, v in blocks.items()},
    }


class ThesslaGreenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        errors: Dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        try:
            result = await validate_input(self.hass, user_input)
        except Exception as e:
            _LOGGER.error("Unexpected error: %s", e)
            errors["base"] = "cannot_connect"
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        await self.async_set_unique_id(f"{result['host']}:{result['port']}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=result["title"],
            data={"host": result["host"], "port": result["port"], "unit": result["unit"]},
            description=f"Model: {result['info']['model']}, FW: {result['info']['firmware']}.",
        )
