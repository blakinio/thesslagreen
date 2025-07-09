from homeassistant.components.number import NumberEntity
from .modbus_map import MODBUS_MAP

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["thesslagreen"][entry.entry_id]
    numbers = [
        ThesslaGreenNumber(coordinator, ent["key"], ent["name"], ent["reg"], ent.get("min", 0), ent.get("max", 100), ent.get("unit", ""), ent.get("scale", 1))
        for ent in MODBUS_MAP if ent["type"] == "number"
    ]
    async_add_entities(numbers)

class ThesslaGreenNumber(NumberEntity):
    def __init__(self, coordinator, key, name, reg, minv, maxv, unit, scale):
        self._coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._reg = reg
        self._attr_min_value = minv
        self._attr_max_value = maxv
        self._attr_unit_of_measurement = unit
        self._scale = scale

    @property
    def value(self):
        return self._coordinator.data.get(self._key)

    async def async_set_value(self, value):
        val = int(value / self._scale)
        await self._coordinator.hass.async_add_executor_job(
            self._coordinator._client.write_register, self._reg, val
        )
        await self._coordinator.async_request_refresh()
