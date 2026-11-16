"""Sesam: open the FRITZ!Box Wi-Fi to new devices for a few minutes."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MINUTES, DOMAIN, MAX_MINUTES, MIN_MINUTES
from .coordinator import (
    STORAGE_VERSION,
    SesamConfigEntry,
    SesamCoordinator,
    storage_key,
)

PLATFORMS = [Platform.BUTTON, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_OPEN = "open"
OPEN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MINUTES): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_MINUTES, max=MAX_MINUTES)
        )
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the open action."""

    async def handle_open(call: ServiceCall) -> None:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="not_set_up"
            )
        await entries[0].runtime_data.async_open(call.data.get(CONF_MINUTES))

    hass.services.async_register(DOMAIN, SERVICE_OPEN, handle_open, schema=OPEN_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SesamConfigEntry) -> bool:
    """Set up Sesam from a config entry."""
    coordinator = SesamCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_cancel_close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SesamConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: SesamConfigEntry) -> None:
    """Drop the stored close time along with the entry."""
    await Store(hass, STORAGE_VERSION, storage_key(entry.entry_id)).async_remove()
