from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN
from .modbus_client import ThesslaGreenClient
import logging

_LOGGER = logging.getLogger(__name__)

class ThesslaGreenCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self._client = ThesslaGreenClient(config["host"], config["port"], config["slave_id"])
        self.data = {}

    async def _async_update_data(self):
        try:
            data = self._client.read_all()
            return data
        except Exception as ex:
            raise UpdateFailed(f"Błąd komunikacji z rekuperatorem: {ex}")

    @property
    def client(self):
        return self._client
