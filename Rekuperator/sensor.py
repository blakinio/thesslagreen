from homeassistant.components.sensor import SensorEntity
from .modbus_map import MODBUS_MAP

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["thesslagreen"][entry.entry_id]
    sensors = [
        ThesslaGreenSensor(coordinator, ent["key"], ent["name"], ent["unit"])
        for ent in MODBUS_MAP if ent["type"] == "sensor"
    ]
    async_add_entities(sensors)

class ThesslaGreenSensor(SensorEntity):
    def __init__(self, coordinator, key, name, unit):
        self._coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._attr_unit_of_measurement = unit

    @property
    def state(self):
        return self._coordinator.data.get(self._key)
