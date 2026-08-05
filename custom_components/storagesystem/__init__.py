"""The Storage System integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import StorageSystemClient
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import StorageSystemCoordinator, result_store
from .frontend import async_register_frontend
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CONVERSATION,
    Platform.SENSOR,
]

type StorageSystemConfigEntry = ConfigEntry[StorageSystemCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: StorageSystemConfigEntry) -> bool:
    """Set up Storage System from a config entry."""
    client = StorageSystemClient(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data.get(CONF_API_KEY),
    )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = StorageSystemCoordinator(hass, entry, client, scan_interval)
    await coordinator.async_load_last_result()

    # Raises ConfigEntryNotReady / ConfigEntryAuthFailed on its own.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await async_register_frontend(hass, Path(__file__).parent)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StorageSystemConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # This entry is still listed while unloading, so 1 means it was the last one.
    if unloaded and len(hass.config_entries.async_entries(DOMAIN)) <= 1:
        async_unload_services(hass)

    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: StorageSystemConfigEntry) -> None:
    """Drop the stored last result when the entry is deleted."""
    await result_store(hass, entry.entry_id).async_remove()


async def _async_update_listener(hass: HomeAssistant, entry: StorageSystemConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
