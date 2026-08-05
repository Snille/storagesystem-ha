"""Serve and auto-register the bundled Lovelace card.

This is what removes the manual copy to /config/www and the manual dashboard
resource entry: the integration hosts the JS itself and asks the frontend to
load it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_CARD_FILENAME, FRONTEND_URL_BASE

_LOGGER = logging.getLogger(__name__)

_REGISTERED_KEY = f"{DOMAIN}_frontend_registered"


def _read_version(component_dir: Path) -> str:
    """Return the manifest version, used to bust the browser cache on upgrade."""
    try:
        manifest = json.loads((component_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "0"
    return str(manifest.get("version") or "0")


async def async_register_frontend(hass: HomeAssistant, component_dir: Path) -> None:
    """Register the card as a static path and load it on every dashboard."""
    if hass.data.get(_REGISTERED_KEY):
        return

    card_path = component_dir / "frontend" / FRONTEND_CARD_FILENAME
    if not await hass.async_add_executor_job(card_path.is_file):
        _LOGGER.warning("Bundled Lovelace card not found at %s", card_path)
        return

    version = await hass.async_add_executor_job(_read_version, component_dir)
    url = f"{FRONTEND_URL_BASE}/{FRONTEND_CARD_FILENAME}"

    await hass.http.async_register_static_paths(
        [StaticPathConfig(url, str(card_path), False)]
    )
    add_extra_js_url(hass, f"{url}?v={version}")

    hass.data[_REGISTERED_KEY] = True
    _LOGGER.debug("Registered Storage System card at %s", url)
