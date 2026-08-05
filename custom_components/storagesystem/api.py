"""Thin async client for the Storage System public REST API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientResponseError, ClientSession

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)


class StorageSystemError(Exception):
    """Base error for the Storage System client."""


class StorageSystemConnectionError(StorageSystemError):
    """The app could not be reached."""


class StorageSystemAuthError(StorageSystemError):
    """The API key was missing or rejected."""


class StorageSystemClient:
    """Talk to the /api/public endpoints of a Storage System instance."""

    def __init__(self, session: ClientSession, base_url: str, api_key: str | None) -> None:
        """Store the connection details."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = (api_key or "").strip()

    @property
    def base_url(self) -> str:
        """Return the normalized base URL of the app."""
        return self._base_url

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key} if self._api_key else {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"

        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status == 401:
                    raise StorageSystemAuthError("Invalid or missing API key.")
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except StorageSystemAuthError:
            raise
        except ClientResponseError as err:
            raise StorageSystemConnectionError(
                f"{method} {path} failed with HTTP {err.status}."
            ) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise StorageSystemConnectionError(f"{method} {path} failed: {err}") from err

        if not isinstance(payload, dict):
            raise StorageSystemConnectionError(f"{method} {path} did not return a JSON object.")

        return payload

    async def async_health(self) -> dict[str, Any]:
        """Return the health payload: {ok, service, date}."""
        return await self._request("GET", "/api/public/health")

    async def async_ask(self, query: str) -> dict[str, Any]:
        """Ask the AI-backed endpoint and return {query, answer, source, count, matches}."""
        return await self._request("POST", "/api/public/ask", json={"query": query})

    async def async_search(self, query: str, limit: int) -> dict[str, Any]:
        """Run a plain search and return {query, count, matches}."""
        return await self._request(
            "GET", "/api/public/search", params={"q": query, "limit": str(limit)}
        )

    async def async_box(self, box_id: str) -> dict[str, Any]:
        """Return a single box by its id."""
        return await self._request("GET", f"/api/public/boxes/{box_id}")
