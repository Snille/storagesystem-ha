"""Health polling plus the shared "latest result" store."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StorageSystemAuthError, StorageSystemClient, StorageSystemError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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

    def async_set_result(self, result: dict[str, Any]) -> None:
        """Store a new ask/search result and push it to every entity."""
        self.last_result = result
        self.async_update_listeners()
