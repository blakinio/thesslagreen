from homeassistant.components.binary_sensor import BinarySensorEntity
from .modbus_map import MODBUS_MAP

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["thesslagreen"][entry.entry_id]
    sensors = [
        ThesslaGreenBinarySensor(coordinator, ent["key"], ent["name"])
        for ent in MODBUS_MAP if ent["type"] == "binary_sensor"
    ]
    async_add_entities(sensors)

class ThesslaGreenBinarySensor(BinarySensorEntity):
    def __init__(self, coordinator, key, name):
        self._coordinator = coordinator
        self._key = key
        self._attr_name = name

    @property
    def is_on(self):
        return bool(self._coordinator.data.get(self._key))
