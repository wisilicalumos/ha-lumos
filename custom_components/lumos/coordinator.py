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

    def __init__(self, hass: HomeAssistant, api: LumosApi) -> None:
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """
        Fetch the latest device list from the Lumos cloud.

        The /wide/1 endpoint already returns live state fields (deviceStatus,
        intensity, cool, rgb) alongside metadata, so a single call serves
        both discovery and state-refresh purposes.
        """
        try:
            if not self.api.is_logged_in:
                _LOGGER.info("Not logged in – attempting re-authentication")
                await self.api.login()

            devices = await self.api.get_devices()

        except LumosAuthError as err:
            # Trigger a re-auth flow in the UI
            raise ConfigEntryAuthFailed(str(err)) from err
        except LumosApiError as err:
            raise UpdateFailed(f"Lumos API error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error fetching Lumos devices: {err}") from err

        return {str(dev["deviceId"]): dev for dev in devices}
