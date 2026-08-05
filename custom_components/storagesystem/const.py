"""Constants for the Storage System integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "storagesystem"

DEFAULT_NAME: Final = "Storage System"
DEFAULT_SCAN_INTERVAL: Final = 60
DEFAULT_SEARCH_LIMIT: Final = 5

CONF_BASE_URL: Final = "base_url"
CONF_API_KEY: Final = "api_key"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_LANGUAGE: Final = "language"
CONF_SPEAK: Final = "speak"
CONF_TTS_ENTITY: Final = "tts_entity"
CONF_MEDIA_PLAYER: Final = "media_player"

LANGUAGES: Final = ["en", "sv", "de"]
DEFAULT_LANGUAGE: Final = "en"

SERVICE_ASK: Final = "ask"
SERVICE_SEARCH: Final = "search"

ATTR_QUERY: Final = "query"
ATTR_LIMIT: Final = "limit"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

# Fired after every successful ask/search. The legacy name is kept so existing
# automations written against the old YAML package keep working.
EVENT_RESULT: Final = "storagesystem_result"
EVENT_RESULT_LEGACY: Final = "lagersystem_result"

# Served from the integration itself, so no manual /config/www copy is needed.
FRONTEND_URL_BASE: Final = "/storagesystem_frontend"
FRONTEND_CARD_FILENAME: Final = "storagesystem-search-card.js"

# Home Assistant rejects state strings longer than this.
MAX_STATE_LENGTH: Final = 255
