"""
Lumos Smart Lighting – Home Assistant custom integration.

Setup sequence:
  1. async_setup_entry – called when the config entry is loaded.
     • Creates a LumosApi instance and logs in.
     • Creates a LumosCoordinator and performs an initial data refresh.
     • Forwards setup to the light platform.
  2. async_unload_entry – tears everything down cleanly.
  3. async_reload_entry – used after a re-auth to pick up a new password.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LumosApi, LumosAuthError, LumosApiError
from .const import (
    CONF_BASE_URL,
    CONF_BUNDLE_ID,
    CONF_BUNDLE_PACKAGE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import LumosCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lumos from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Build the API client, reusing HA's shared aiohttp session
    session = async_get_clientsession(hass)
    api = LumosApi(
        base_url=entry.data[CONF_BASE_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        bundle_id=entry.data[CONF_BUNDLE_ID],
        bundle_package=entry.data[CONF_BUNDLE_PACKAGE],
        session=session,
    )

    # Authenticate
    try:
        await api.login()
    except LumosAuthError as err:
        raise ConfigEntryAuthFailed(
            f"Lumos authentication failed: {err}"
        ) from err
    except LumosApiError as err:
        raise ConfigEntryNotReady(
            f"Lumos API not reachable during setup: {err}"
        ) from err

    # Build coordinator
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    coordinator = LumosCoordinator(hass, api)

    # First refresh – raise ConfigEntryNotReady on failure so HA retries
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Lumos initial data fetch failed: {err}"
        ) from err

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms (currently just "light")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates (e.g. changed polling interval)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.info(
        "Lumos integration set up successfully. "
        "Devices found: %d",
        len(coordinator.data),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Lumos config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: LumosCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        # The API client uses HA's shared session so we don't close it here
        _LOGGER.info("Lumos integration unloaded.")
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a Lumos config entry (e.g. after re-auth)."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update – reload to apply new polling interval."""
    await hass.config_entries.async_reload(entry.entry_id)
