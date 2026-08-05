"""Shared ask/search logic used by both the services and the conversation agent."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import StorageSystemError
from .const import (
    CONF_MEDIA_PLAYER,
    CONF_SPEAK,
    CONF_TTS_ENTITY,
    EVENT_RESULT,
    EVENT_RESULT_LEGACY,
)
from .result import build_error_result, build_result

_LOGGER = logging.getLogger(__name__)


def publish_result(
    hass: HomeAssistant, entry: ConfigEntry, result: dict[str, Any]
) -> None:
    """Store the result on the coordinator and fire the result events."""
    entry.runtime_data.async_set_result(result)

    event_data = {**result, "entry_id": entry.entry_id}
    hass.bus.async_fire(EVENT_RESULT, event_data)
    hass.bus.async_fire(EVENT_RESULT_LEGACY, event_data)


async def async_speak(
    hass: HomeAssistant,
    entry: ConfigEntry,
    message: str,
    *,
    speak: bool | None = None,
    tts_entity: str | None = None,
    media_player: str | None = None,
) -> None:
    """Read the answer out loud when TTS is configured and not overridden off."""
    if not message:
        return

    if speak is None:
        speak = entry.options.get(CONF_SPEAK, False)
    if not speak:
        return

    tts_entity = tts_entity or entry.options.get(CONF_TTS_ENTITY)
    media_player = media_player or entry.options.get(CONF_MEDIA_PLAYER)

    if not tts_entity or not media_player:
        _LOGGER.warning(
            "Storage System was asked to speak but no TTS entity and media player are configured"
        )
        return

    try:
        await hass.services.async_call(
            "tts",
            "speak",
            {
                "entity_id": tts_entity,
                "media_player_entity_id": media_player,
                "message": message,
            },
            blocking=False,
        )
    except HomeAssistantError as err:
        _LOGGER.warning("Storage System could not speak the answer: %s", err)


async def async_ask(
    hass: HomeAssistant, entry: ConfigEntry, query: str
) -> dict[str, Any]:
    """Ask the AI endpoint, publish the result, and return it.

    On failure the entities are still filled with safe fallbacks before the
    error propagates, so a dashboard never shows a stale answer as if it were
    the response to the latest question.
    """
    try:
        payload = await entry.runtime_data.client.async_ask(query)
    except StorageSystemError as err:
        publish_result(hass, entry, build_error_result(mode="ask", query=query, message=str(err)))
        raise HomeAssistantError(f"Storage System ask failed: {err}") from err

    result = build_result(payload, mode="ask", query=query)
    publish_result(hass, entry, result)
    return result


async def async_search(
    hass: HomeAssistant, entry: ConfigEntry, query: str, limit: int
) -> dict[str, Any]:
    """Run a plain search, publish the result, and return it."""
    try:
        payload = await entry.runtime_data.client.async_search(query, limit)
    except StorageSystemError as err:
        publish_result(
            hass, entry, build_error_result(mode="search", query=query, message=str(err))
        )
        raise HomeAssistantError(f"Storage System search failed: {err}") from err

    result = build_result(payload, mode="search", query=query)
    publish_result(hass, entry, result)
    return result
