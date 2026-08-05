"""Flatten API payloads into the result shape the entities and events expose.

This mirrors what the old YAML package built with a few hundred lines of Jinja
templates: take the first match and hoist its interesting fields to the top.
"""

from __future__ import annotations

from typing import Any


def _first_match(payload: dict[str, Any]) -> dict[str, Any]:
    matches = payload.get("matches")
    if isinstance(matches, list) and matches and isinstance(matches[0], dict):
        return matches[0]
    return {}


def _location_text(match: dict[str, Any]) -> str:
    location = match.get("location")
    if not isinstance(location, dict):
        return ""

    parts = [
        str(location.get("system") or "").strip(),
        str(location.get("shelf") or "").strip(),
        str(location.get("slot") or "").strip(),
    ]
    return ", ".join(part for part in parts if part)


def build_result(payload: dict[str, Any], *, mode: str, query: str) -> dict[str, Any]:
    """Return the flat result dict used by entities, the event, and the card."""
    match = _first_match(payload)
    photos = match.get("photos")
    photos = photos if isinstance(photos, list) else []
    first_photo = photos[0] if photos and isinstance(photos[0], dict) else {}

    keywords = match.get("itemKeywords")
    keywords = [str(item) for item in keywords] if isinstance(keywords, list) else []

    count = payload.get("count")
    match_count = int(count) if isinstance(count, (int, float)) else len(
        payload.get("matches") or []
    )

    return {
        "mode": mode,
        "query": query,
        "answer": str(payload.get("answer") or "").strip(),
        "source": str(payload.get("source") or mode),
        "match_count": match_count,
        "box_id": str(match.get("boxId") or ""),
        "label": str(match.get("label") or ""),
        "location": _location_text(match),
        "location_id": str(match.get("locationId") or ""),
        "session_id": str(match.get("sessionId") or ""),
        "summary": str(match.get("summary") or ""),
        "keywords": keywords,
        "photo_count": len(photos),
        "thumbnail_url": str(first_photo.get("thumbnailUrl") or ""),
        "original_url": str(first_photo.get("originalUrl") or ""),
        "matches": payload.get("matches") or [],
        "error": "",
    }


def build_error_result(*, mode: str, query: str, message: str) -> dict[str, Any]:
    """Return a result with safe fallbacks so entities never go stale on failure."""
    return {
        "mode": mode,
        "query": query,
        "answer": "",
        "source": "api_error",
        "match_count": 0,
        "box_id": "",
        "label": "",
        "location": "",
        "location_id": "",
        "session_id": "",
        "summary": "",
        "keywords": [],
        "photo_count": 0,
        "thumbnail_url": "",
        "original_url": "",
        "matches": [],
        "error": message,
    }
