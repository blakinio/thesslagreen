from homeassistant.components.select import SelectEntity
from .modbus_map import MODBUS_MAP

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["thesslagreen"][entry.entry_id]
    selects = [
        ThesslaGreenSelect(coordinator, ent["key"], ent["name"], ent["options"], ent["reg"])
        for ent in MODBUS_MAP if ent["type"] == "select"
    ]
    async_add_entities(selects)

class ThesslaGreenSelect(SelectEntity):
    def __init__(self, coordinator, key, name, options, reg):
        self._coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._attr_options = list(options.values())
        self._map = {v: k for k, v in options.items()}
        self._reg = reg

    @property
    def current_option(self):
        val = self._coordinator.data.get(self._key)
        for k, v in self._map.items():
            if v == val:
                return k
        return None

    async def async_select_option(self, option):
        value = self._map.get(option, 0)
        await self._coordinator.hass.async_add_executor_job(
            self._coordinator._client.write_register, self._reg, value
        )
        await self._coordinator.async_request_refresh()
