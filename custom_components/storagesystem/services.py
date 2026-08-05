"""The storagesystem.ask and storagesystem.search services."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .actions import async_ask, async_search, async_speak
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LIMIT,
    ATTR_QUERY,
    CONF_MEDIA_PLAYER,
    CONF_SPEAK,
    CONF_TTS_ENTITY,
    DEFAULT_SEARCH_LIMIT,
    DOMAIN,
    SERVICE_ASK,
    SERVICE_SEARCH,
)

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


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration-level services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ASK):
        return

    async def async_handle_ask(call: ServiceCall) -> ServiceResponse:
        """Ask the AI endpoint, store the answer, and optionally speak it."""
        entry = _resolve_entry(hass, call)
        result = await async_ask(hass, entry, call.data[ATTR_QUERY])

        await async_speak(
            hass,
            entry,
            result["answer"],
            speak=call.data.get(CONF_SPEAK),
            tts_entity=call.data.get(CONF_TTS_ENTITY),
            media_player=call.data.get(CONF_MEDIA_PLAYER),
        )
        return result

    async def async_handle_search(call: ServiceCall) -> ServiceResponse:
        """Run a plain search and store the top match."""
        entry = _resolve_entry(hass, call)
        return await async_search(
            hass, entry, call.data[ATTR_QUERY], call.data.get(ATTR_LIMIT, DEFAULT_SEARCH_LIMIT)
        )

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
