"""
Lumos Smart Lighting – Home Assistant custom integration.

Setup sequence:
  1. async_setup_entry – called when the config entry is loaded.
     • Creates a LumosApi instance and logs in.
     • Creates a LumosCoordinator and performs an initial data refresh.
     • Forwards setup to the light platform.
  2. async_unload_entry – tears everything down cleanly.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LumosApi, LumosAuthError, LumosApiError, generate_device_id
from .const import (
    CONF_BASE_URL,
    CONF_BUNDLE_ID,
    CONF_BUNDLE_PACKAGE,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import LumosCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older config entries.

    1.1 -> 1.2: add a random device id (replaces the host MAC address that
    was read with uuid.getnode() on the event loop).
    """
    if entry.version > 1:
        # Downgrade from a future version is not supported
        return False

    if entry.minor_version < 2:
        data = {**entry.data}
        data.setdefault(CONF_DEVICE_ID, generate_device_id())
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
        _LOGGER.debug("Migrated Lumos config entry to version 1.2")

    return True


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
        device_id=entry.data[CONF_DEVICE_ID],
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
    coordinator = LumosCoordinator(hass, api, scan_interval)

    # Raises ConfigEntryNotReady on UpdateFailed and propagates
    # ConfigEntryAuthFailed so the reauth flow starts.
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
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


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update – reload to apply new polling interval."""
    await hass.config_entries.async_reload(entry.entry_id)
