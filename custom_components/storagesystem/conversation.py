"""Conversation agent that forwards every utterance to the storage system.

Point an Assist pipeline at this agent and the satellite using that pipeline
becomes a dedicated storage-search kiosk: whatever you say is sent straight to
/api/public/ask and the answer is spoken back by the satellite that asked. No
wake prefix, no sentence matching.

Because the satellite speaks the answer itself, this path never triggers the
integration's own TTS option — that would say everything twice.
"""

from __future__ import annotations

import logging
import re

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StorageSystemConfigEntry
from .actions import async_ask
from .const import (
    CONF_ENABLE_CONVERSATION,
    CONF_LANGUAGE,
    DEFAULT_LANGUAGE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Spoken fallbacks per configured language.
FALLBACKS = {
    "en": {
        "no_answer": "I could not find a clear answer.",
        "no_contact": "I could not reach the storage system right now.",
    },
    "sv": {
        "no_answer": "Jag hittade inget tydligt svar.",
        "no_contact": "Jag kunde inte kontakta verkstan just nu.",
    },
    "de": {
        "no_answer": "Ich habe keine eindeutige Antwort gefunden.",
        "no_contact": "Ich konnte das Lagersystem gerade nicht erreichen.",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StorageSystemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the conversation agent when the option is enabled."""
    if not entry.options.get(CONF_ENABLE_CONVERSATION, True):
        return

    async_add_entities([StorageSystemConversationEntity(entry)])


class StorageSystemConversationEntity(ConversationEntity):
    """Sends each utterance verbatim to the storage system."""

    _attr_has_entity_name = True
    # No name of its own: the agent is the device's main feature, so it takes
    # the device name and lands on conversation.storage_system.
    _attr_name = None

    def __init__(self, entry: StorageSystemConfigEntry) -> None:
        """Set up the agent for one instance."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_conversation"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def supported_languages(self) -> str:
        """Match every language — the raw text is forwarded regardless."""
        return MATCH_ALL

    def _fallback(self, key: str) -> str:
        language = self._entry.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        return FALLBACKS.get(language, FALLBACKS[DEFAULT_LANGUAGE])[key]

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Forward the recognized text and return the answer as speech.

        async_process is overridden rather than _async_handle_message because
        this is a stateless passthrough, not an LLM that needs chat history.
        """
        response = intent.IntentResponse(language=user_input.language)
        query = (user_input.text or "").strip()

        if not query:
            response.async_set_speech(self._fallback("no_answer"))
            return ConversationResult(
                response=response, conversation_id=user_input.conversation_id
            )

        try:
            result = await async_ask(self.hass, self._entry, query)
            answer = result["answer"] or self._fallback("no_answer")
        except HomeAssistantError as err:
            # Never let the satellite hang waiting for an answer that won't come.
            _LOGGER.warning("Storage System request failed for query %r: %s", query, err)
            answer = self._fallback("no_contact")

        # The storage system separates clauses with semicolons, which most TTS
        # engines barely pause on — the answer comes out as one rushed run-on
        # sentence. Swap them for periods so each clause gets a real stop.
        answer = re.sub(r";\s*", ". ", answer)

        response.async_set_speech(answer)
        return ConversationResult(
            response=response, conversation_id=user_input.conversation_id
        )
