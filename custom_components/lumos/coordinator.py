"""
DataUpdateCoordinator for the Lumos integration.

Polls the Lumos cloud API on a fixed interval and stores the latest
device state as a dict keyed by deviceId string.  All platform entities
subscribe to this coordinator so that a single HTTP round-trip refreshes
every entity at once.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LumosApi, LumosApiError, LumosAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LumosCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """
    Manages periodic data refresh from the Lumos cloud.

    coordinator.data is a dict:
      {
        "<deviceId>": {
          "deviceId": ...,
          "deviceName": ...,
          "deviceMeshId": ...,
          "deviceStatus": ...,
          "intensity": ...,
          "cool": ...,
          "rgb": "255,128,0",
          ...
        },
        ...
      }
    """

    def __init__(self, hass: HomeAssistant, api: LumosApi, scan_interval: int = DEFAULT_SCAN_INTERVAL) -> None:
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """
        Fetch the latest device list from the Lumos cloud.

        The /wide/1 endpoint already returns live state fields (deviceStatus,
        intensity, cool, rgb) alongside metadata, so a single call serves
        both discovery and state-refresh purposes.
        """
        try:
            return await self._fetch()
        except LumosAuthError as err:
            # Session token rejected (e.g. superseded by a newer login).
            # LumosApi has cleared it; log in again and retry once. Only a
            # rejected login raises ConfigEntryAuthFailed.
            _LOGGER.debug("Lumos session rejected (%s) – logging in again", err)
        try:
            return await self._fetch()
        except LumosAuthError as err:
            raise UpdateFailed(f"Lumos session rejected after re-login: {err}") from err

    async def _fetch(self) -> dict[str, dict[str, Any]]:
        """Log in if needed, then fetch all devices."""
        if not self.api.is_logged_in:
            try:
                await self.api.login()
            except LumosAuthError as err:
                # The cloud rejected the stored credentials: ask the user.
                raise ConfigEntryAuthFailed(str(err)) from err
            except LumosApiError as err:
                raise UpdateFailed(f"Lumos login failed: {err}") from err

        try:
            devices = await self.api.get_devices()
        except LumosAuthError:
            raise
        except LumosApiError as err:
            raise UpdateFailed(f"Lumos API error: {err}") from err

        return {str(dev["deviceId"]): dev for dev in devices}
