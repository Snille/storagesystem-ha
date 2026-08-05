"""Shared entity base for Storage System."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import StorageSystemCoordinator


class StorageSystemEntity(CoordinatorEntity[StorageSystemCoordinator]):
    """Base entity tied to one Storage System instance."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: StorageSystemCoordinator, key: str) -> None:
        """Attach the entity to the instance device."""
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or DEFAULT_NAME,
            manufacturer="Snille",
            model="Storage System",
            configuration_url=coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        """Result entities stay available even while the API is briefly down."""
        return True
