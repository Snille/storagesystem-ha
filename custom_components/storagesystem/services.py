"""The storagesystem.ask and storagesystem.search services."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import StorageSystemError
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LIMIT,
    ATTR_QUERY,
    CONF_MEDIA_PLAYER,
    CONF_SPEAK,
    CONF_TTS_ENTITY,
    DEFAULT_SEARCH_LIMIT,
    DOMAIN,
    EVENT_RESULT,
    EVENT_RESULT_LEGACY,
    SERVICE_ASK,
    SERVICE_SEARCH,
)
from .result import build_error_result, build_result

_LOGGER = logging.getLogger(__name__)

# Trim here so the handlers always receive a non-empty query.
QUERY = vol.All(cv.string, vol.Strip, vol.Length(min=1))

ASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_QUERY): QUERY,
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(CONF_SPEAK): cv.boolean,
        vol.Optional(CONF_TTS_ENTITY): cv.entity_id,
        vol.Optional(CONF_MEDIA_PLAYER): cv.entity_id,
    }
)

SEARCH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_QUERY): QUERY,
        vol.Optional(ATTR_LIMIT, default=DEFAULT_SEARCH_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=50)
        ),
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


def _resolve_entry(hass: HomeAssistant, call: ServiceCall) -> ConfigEntry:
    """Return the config entry the call targets, defaulting to the only one."""
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]

    if entry_id:
        for entry in loaded:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError(
            f"No loaded Storage System config entry with id {entry_id}."
        )

    if not loaded:
        raise ServiceValidationError("No loaded Storage System config entry.")
    if len(loaded) > 1:
        raise ServiceValidationError(
            "Multiple Storage System instances are configured. "
            f"Pass {ATTR_CONFIG_ENTRY_ID} to choose one."
        )

    return loaded[0]


async def _async_speak(
    hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall, message: str
) -> None:
    """Read the answer out loud, if TTS is configured and not overridden off."""
    if not message:
        return

    speak = call.data.get(CONF_SPEAK, entry.options.get(CONF_SPEAK, False))
    if not speak:
        return

    tts_entity = call.data.get(CONF_TTS_ENTITY) or entry.options.get(CONF_TTS_ENTITY)
    media_player = call.data.get(CONF_MEDIA_PLAYER) or entry.options.get(CONF_MEDIA_PLAYER)

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


def _publish(hass: HomeAssistant, entry: ConfigEntry, result: dict[str, Any]) -> None:
    """Store the result on the coordinator and fire the result events."""
    entry.runtime_data.async_set_result(result)

    event_data = {**result, "entry_id": entry.entry_id}
    hass.bus.async_fire(EVENT_RESULT, event_data)
    hass.bus.async_fire(EVENT_RESULT_LEGACY, event_data)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration-level services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ASK):
        return

    async def async_handle_ask(call: ServiceCall) -> ServiceResponse:
        """Ask the AI endpoint, store the answer, and optionally speak it."""
        entry = _resolve_entry(hass, call)
        query = call.data[ATTR_QUERY]

        try:
            payload = await entry.runtime_data.client.async_ask(query)
        except StorageSystemError as err:
            result = build_error_result(mode="ask", query=query, message=str(err))
            _publish(hass, entry, result)
            raise HomeAssistantError(f"Storage System ask failed: {err}") from err

        result = build_result(payload, mode="ask", query=query)
        _publish(hass, entry, result)
        await _async_speak(hass, entry, call, result["answer"])
        return result

    async def async_handle_search(call: ServiceCall) -> ServiceResponse:
        """Run a plain search and store the top match."""
        entry = _resolve_entry(hass, call)
        query = call.data[ATTR_QUERY]
        limit = call.data.get(ATTR_LIMIT, DEFAULT_SEARCH_LIMIT)

        try:
            payload = await entry.runtime_data.client.async_search(query, limit)
        except StorageSystemError as err:
            result = build_error_result(mode="search", query=query, message=str(err))
            _publish(hass, entry, result)
            raise HomeAssistantError(f"Storage System search failed: {err}") from err

        result = build_result(payload, mode="search", query=query)
        _publish(hass, entry, result)
        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_ASK,
        async_handle_ask,
        schema=ASK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH,
        async_handle_search,
        schema=SEARCH_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the services when the last config entry goes away."""
    hass.services.async_remove(DOMAIN, SERVICE_ASK)
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH)
