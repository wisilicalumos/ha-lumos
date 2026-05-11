"""
Config flow for the Lumos Smart Lighting integration.

Provides a UI-based setup wizard that:
  1. Asks the user for the Lumos cloud URL, credentials, and app bundle info.
  2. Validates by attempting a real login.
  3. Stores the credentials in a ConfigEntry.

A re-auth flow is also provided so that HA can prompt the user to update
their password if a token becomes invalid at runtime.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LumosApi, LumosAuthError, LumosApiError
from .const import (
    CONF_BASE_URL,
    CONF_BUNDLE_ID,
    CONF_BUNDLE_PACKAGE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_BUNDLE_ID,
    DEFAULT_BUNDLE_PACKAGE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Form schemas
# --------------------------------------------------------------------------

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, description={"suggested_value": "https://lumos.wisilica.com"}): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=3600)
        ),
    }
)


async def _validate_credentials(
    hass,
    base_url: str,
    username: str,
    password: str,
    bundle_id: str,
    bundle_package: str,
) -> dict[str, str]:
    """
    Attempt app registration + login and return errors dict.
    Returns {} on success.
    """
    session = async_get_clientsession(hass)
    api = LumosApi(base_url, username, password, bundle_id, bundle_package, session=session)
    try:
        await api.login()
    except LumosAuthError:
        return {"base": "invalid_auth"}
    except LumosApiError:
        return {"base": "cannot_connect"}
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error during Lumos credential validation")
        return {"base": "unknown"}
    return {}


class LumosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lumos."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

    # ------------------------------------------------------------------
    # Initial setup step
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            base_url: str = user_input[CONF_BASE_URL].rstrip("/")
            username: str = user_input[CONF_USERNAME]
            password: str = user_input[CONF_PASSWORD]

            # Prevent duplicate entries for the same account
            await self.async_set_unique_id(f"{base_url}_{username}")
            self._abort_if_unique_id_configured()

            errors = await _validate_credentials(
                self.hass, base_url, username, password, DEFAULT_BUNDLE_ID, DEFAULT_BUNDLE_PACKAGE
            )

            if not errors:
                return self.async_create_entry(
                    title=f"Lumos ({username})",
                    data={
                        CONF_BASE_URL: base_url,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_BUNDLE_ID: DEFAULT_BUNDLE_ID,
                        CONF_BUNDLE_PACKAGE: DEFAULT_BUNDLE_PACKAGE,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://docs.wisilica.com/lumos",
            },
        )

    # ------------------------------------------------------------------
    # Re-authentication step (triggered when token expires at runtime)
    # ------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self._reauth_entry

        if user_input is not None and entry:
            new_password: str = user_input[CONF_PASSWORD]
            errors = await _validate_credentials(
                self.hass,
                entry.data[CONF_BASE_URL],
                entry.data[CONF_USERNAME],
                new_password, DEFAULT_BUNDLE_ID, DEFAULT_BUNDLE_PACKAGE,
            )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_PASSWORD: new_password}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Options flow hook
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LumosOptionsFlow:
        return LumosOptionsFlow(config_entry)


class LumosOptionsFlow(OptionsFlow):
    """Handle Lumos integration options (e.g. polling interval)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_scan = self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("scan_interval", default=current_scan): vol.All(
                        int, vol.Range(min=10, max=3600)
                    ),
                }
            ),
        )
