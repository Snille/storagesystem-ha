"""Connectivity sensor for the Storage System API."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StorageSystemConfigEntry
from .coordinator import StorageSystemCoordinator
from .entity import StorageSystemEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StorageSystemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the API connectivity sensor."""
    async_add_entities([StorageSystemApiSensor(entry.runtime_data)])


class StorageSystemApiSensor(StorageSystemEntity, BinarySensorEntity):
    """Replaces the REST sensor that reported online/offline."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "api"

    def __init__(self, coordinator: StorageSystemCoordinator) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, "api")

    @property
    def is_on(self) -> bool:
        """Return True while the app answers /api/public/health with ok."""
        return self.coordinator.api_online

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the instance URL and the service name it reports."""
        data = self.coordinator.data or {}
        return {
            "base_url": self.coordinator.client.base_url,
            "service": data.get("service"),
        }
