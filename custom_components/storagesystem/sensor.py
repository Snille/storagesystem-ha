"""Sensors exposing the latest Storage System result and API status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StorageSystemConfigEntry
from .const import STATE_DISPLAY_LENGTH
from .coordinator import StorageSystemCoordinator
from .entity import StorageSystemEntity


@dataclass(frozen=True, kw_only=True)
class StorageSystemSensorDescription(SensorEntityDescription):
    """Describes a sensor fed from the latest result."""

    value_fn: Callable[[dict[str, Any]], Any]
    display_fn: Callable[[str], str] | None = None


def _text(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda result: result.get(key) or None


def _short_url(url: str) -> str:
    """Render an asset URL as something readable, e.g. ``d716cc5f…/thumbnail``.

    Signed asset URLs are ~120 characters of host, uuid and key, none of which
    says anything at a glance. The full URL stays in the full_value attribute.
    """
    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    if len(segments) < 2:
        return url
    asset_id, kind = segments[-2], segments[-1]
    return f"{asset_id.split('-')[0]}…/{kind}"


RESULT_SENSORS: tuple[StorageSystemSensorDescription, ...] = (
    StorageSystemSensorDescription(
        key="latest_query",
        translation_key="latest_query",
        icon="mdi:magnify",
        value_fn=_text("query"),
    ),
    StorageSystemSensorDescription(
        key="latest_answer",
        translation_key="latest_answer",
        icon="mdi:comment-text-outline",
        value_fn=_text("answer"),
    ),
    StorageSystemSensorDescription(
        key="latest_location",
        translation_key="latest_location",
        icon="mdi:map-marker",
        value_fn=_text("location"),
    ),
    StorageSystemSensorDescription(
        key="latest_location_id",
        translation_key="latest_location_id",
        icon="mdi:identifier",
        entity_registry_enabled_default=False,
        value_fn=_text("location_id"),
    ),
    StorageSystemSensorDescription(
        key="latest_box_id",
        translation_key="latest_box_id",
        icon="mdi:package-variant-closed",
        value_fn=_text("box_id"),
    ),
    StorageSystemSensorDescription(
        key="latest_label",
        translation_key="latest_label",
        icon="mdi:label-outline",
        value_fn=_text("label"),
    ),
    StorageSystemSensorDescription(
        key="latest_session_id",
        translation_key="latest_session_id",
        icon="mdi:identifier",
        entity_registry_enabled_default=False,
        value_fn=_text("session_id"),
    ),
    StorageSystemSensorDescription(
        key="latest_source",
        translation_key="latest_source",
        icon="mdi:source-branch",
        value_fn=_text("source"),
    ),
    StorageSystemSensorDescription(
        key="latest_summary",
        translation_key="latest_summary",
        icon="mdi:text-short",
        value_fn=_text("summary"),
    ),
    StorageSystemSensorDescription(
        key="latest_keywords",
        translation_key="latest_keywords",
        icon="mdi:tag-multiple-outline",
        value_fn=lambda result: ", ".join(result.get("keywords") or []) or None,
    ),
    StorageSystemSensorDescription(
        key="latest_thumbnail_url",
        translation_key="latest_thumbnail_url",
        icon="mdi:image-outline",
        # Raw asset URLs are plumbing for the card, not something to read in the
        # main sensor list, so they live in the collapsed diagnostic section.
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_text("thumbnail_url"),
        display_fn=_short_url,
    ),
    StorageSystemSensorDescription(
        key="latest_original_url",
        translation_key="latest_original_url",
        icon="mdi:image",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_text("original_url"),
        display_fn=_short_url,
    ),
    StorageSystemSensorDescription(
        key="latest_match_count",
        translation_key="latest_match_count",
        icon="mdi:counter",
        native_unit_of_measurement="matches",
        value_fn=lambda result: result.get("match_count"),
    ),
    StorageSystemSensorDescription(
        key="latest_photo_count",
        translation_key="latest_photo_count",
        icon="mdi:image-multiple-outline",
        native_unit_of_measurement="photos",
        value_fn=lambda result: result.get("photo_count"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StorageSystemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storage System sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        StorageSystemResultSensor(coordinator, description) for description in RESULT_SENSORS
    ]
    entities.append(StorageSystemApiTimestampSensor(coordinator))
    async_add_entities(entities)


class StorageSystemResultSensor(StorageSystemEntity, SensorEntity):
    """A single field of the latest ask/search result."""

    entity_description: StorageSystemSensorDescription

    def __init__(
        self,
        coordinator: StorageSystemCoordinator,
        description: StorageSystemSensorDescription,
    ) -> None:
        """Set up the sensor from its description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _display(self, value: Any) -> Any:
        """Shorten a value so it stays on one or two lines in the UI."""
        if not isinstance(value, str):
            return value
        if display_fn := self.entity_description.display_fn:
            value = display_fn(value)
        if len(value) > STATE_DISPLAY_LENGTH:
            return f"{value[: STATE_DISPLAY_LENGTH - 1]}…"
        return value

    @property
    def native_value(self) -> Any:
        """Return the value, shortened to keep the UI layout intact."""
        return self._display(self.entity_description.value_fn(self.coordinator.last_result))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the untruncated value and the query it came from."""
        result = self.coordinator.last_result
        if not result:
            return None

        attributes: dict[str, Any] = {
            "query": result.get("query"),
            "mode": result.get("mode"),
        }

        value = self.entity_description.value_fn(result)
        if isinstance(value, str) and self._display(value) != value:
            attributes["full_value"] = value

        if self.entity_description.key == "latest_keywords":
            attributes["keywords"] = result.get("keywords") or []

        if error := result.get("error"):
            attributes["error"] = error

        return attributes


class StorageSystemApiTimestampSensor(StorageSystemEntity, SensorEntity):
    """Since when the app has been answering health polls.

    This used to report the ``date`` field straight from every health payload,
    which is the app's current clock and therefore changed on every poll — one
    logbook entry and one recorder row per minute, saying nothing the
    connectivity sensor does not already say. It now only moves when the
    connection actually changes state.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "api_timestamp"

    def __init__(self, coordinator: StorageSystemCoordinator) -> None:
        """Set up the timestamp sensor."""
        super().__init__(coordinator, "api_timestamp")
        self._connected_since: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Seed the timestamp from the refresh that ran before setup."""
        await super().async_added_to_hass()
        self._track_connection()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Move the timestamp only across a connected/disconnected edge."""
        self._track_connection()
        super()._handle_coordinator_update()

    def _track_connection(self) -> None:
        if not self.coordinator.last_update_success:
            self._connected_since = None
        elif self._connected_since is None:
            raw = (self.coordinator.data or {}).get("date")
            parsed = dt_util.parse_datetime(raw) if isinstance(raw, str) else None
            self._connected_since = parsed or dt_util.utcnow()

    @property
    def available(self) -> bool:
        """Only meaningful while health polling works."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> datetime | None:
        """Return when the app was first seen healthy in the current stretch."""
        return self._connected_since
