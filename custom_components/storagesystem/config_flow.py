"""Config and options flow for Storage System."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import StorageSystemAuthError, StorageSystemClient, StorageSystemError
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_ENABLE_CONVERSATION,
    CONF_LANGUAGE,
    CONF_MEDIA_PLAYER,
    CONF_SCAN_INTERVAL,
    CONF_SPEAK,
    CONF_TTS_ENTITY,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LANGUAGES,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_API_KEY, default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _normalize_base_url(base_url: str) -> str:
    """Strip trailing slashes and any accidentally pasted API path."""
    value = base_url.strip().rstrip("/")
    for suffix in ("/api/public/health", "/api/public/ask", "/api/public/search", "/api/public"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value.rstrip("/")


async def _async_validate(hass, base_url: str, api_key: str) -> None:
    """Raise if the instance cannot be reached or rejects the key."""
    client = StorageSystemClient(async_get_clientsession(hass), base_url, api_key)
    await client.async_health()


class StorageSystemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup of a Storage System instance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the base URL and API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base_url = _normalize_base_url(user_input[CONF_BASE_URL])
            api_key = (user_input.get(CONF_API_KEY) or "").strip()

            if not base_url.startswith(("http://", "https://")):
                errors[CONF_BASE_URL] = "invalid_url"
            else:
                await self.async_set_unique_id(base_url.lower())
                self._abort_if_unique_id_configured()

                try:
                    await _async_validate(self.hass, base_url, api_key)
                except StorageSystemAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                except StorageSystemError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data={CONF_BASE_URL: base_url, CONF_API_KEY: api_key},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the API key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            try:
                await _async_validate(self.hass, entry.data[CONF_BASE_URL], api_key)
            except StorageSystemAuthError:
                errors[CONF_API_KEY] = "invalid_auth"
            except StorageSystemError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_API_KEY, default=""): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"base_url": entry.data[CONF_BASE_URL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return StorageSystemOptionsFlow()


class StorageSystemOptionsFlow(OptionsFlow):
    """Polling interval, card language, and optional spoken answers."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=3600, step=10, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_LANGUAGE,
                    default=options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                ): SelectSelector(
                    SelectSelectorConfig(options=LANGUAGES, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Optional(
                    CONF_ENABLE_CONVERSATION,
                    default=options.get(CONF_ENABLE_CONVERSATION, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SPEAK, default=options.get(CONF_SPEAK, False)
                ): BooleanSelector(),
                vol.Optional(
                    CONF_TTS_ENTITY,
                    description={"suggested_value": options.get(CONF_TTS_ENTITY)},
                ): EntitySelector(EntitySelectorConfig(domain="tts")),
                vol.Optional(
                    CONF_MEDIA_PLAYER,
                    description={"suggested_value": options.get(CONF_MEDIA_PLAYER)},
                ): EntitySelector(EntitySelectorConfig(domain="media_player")),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
