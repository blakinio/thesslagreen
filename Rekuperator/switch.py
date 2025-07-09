from homeassistant.components.switch import SwitchEntity
from .modbus_map import MODBUS_MAP

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["thesslagreen"][entry.entry_id]
    switches = [
        ThesslaGreenSwitch(coordinator, ent["key"], ent["name"], ent["reg"])
        for ent in MODBUS_MAP if ent["type"] == "switch"
    ]
    async_add_entities(switches)

class ThesslaGreenSwitch(SwitchEntity):
    def __init__(self, coordinator, key, name, reg):
        self._coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._reg = reg

    @property
    def is_on(self):
        return bool(self._coordinator.data.get(self._key))

    async def async_turn_on(self):
        await self._coordinator.hass.async_add_executor_job(
            self._coordinator._client.write_register, self._reg, 1
        )
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self):
        await self._coordinator.hass.async_add_executor_job(
            self._coordinator._client.write_register, self._reg, 0
        )
        await self._coordinator.async_request_refresh()
