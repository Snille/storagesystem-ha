"""Health polling plus the shared "latest result" store."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StorageSystemAuthError, StorageSystemClient, StorageSystemError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SAVE_DELAY = 5


def result_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the store holding the latest result for one config entry."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


class StorageSystemCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll /api/public/health and hold the latest ask/search result."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: StorageSystemClient,
        scan_interval: int,
    ) -> None:
        """Set up the coordinator for one configured Storage System instance."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self.client = client
        self.last_result: dict[str, Any] = {}
        self._store = result_store(hass, entry.entry_id)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_health()
        except StorageSystemAuthError as err:
            # The coordinator turns this into a reauth prompt in the UI.
            raise ConfigEntryAuthFailed(str(err)) from err
        except StorageSystemError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def api_online(self) -> bool:
        """Return whether the last health poll succeeded."""
        return bool(self.last_update_success and (self.data or {}).get("ok"))

    async def async_load_last_result(self) -> None:
        """Restore the last result so a restart does not blank the sensors.

        The YAML package this integration replaces kept the last answer in
        input_text helpers, which Home Assistant restores automatically. Without
        this the dashboard would go empty on every restart.
        """
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self.last_result = stored

    def async_set_result(self, result: dict[str, Any]) -> None:
        """Store a new ask/search result and push it to every entity."""
        self.last_result = result
        self._store.async_delay_save(lambda: self.last_result, SAVE_DELAY)
        self.async_update_listeners()
