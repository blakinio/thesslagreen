from homeassistant.components.button import ButtonEntity
from .modbus_map import MODBUS_MAP

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["thesslagreen"][entry.entry_id]
    buttons = [
        ThesslaGreenButton(coordinator, ent["key"], ent["name"], ent["reg"], ent.get("value", 1))
        for ent in MODBUS_MAP if ent["type"] == "button"
    ]
    async_add_entities(buttons)

class ThesslaGreenButton(ButtonEntity):
    def __init__(self, coordinator, key, name, reg, value):
        self._coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._reg = reg
        self._value = value

    async def async_press(self):
        await self._coordinator.hass.async_add_executor_job(
            self._coordinator._client.write_register, self._reg, self._value
        )
        await self._coordinator.async_request_refresh()
