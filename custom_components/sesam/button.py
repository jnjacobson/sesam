"""The button that opens the Wi-Fi for a few minutes."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SesamConfigEntry
from .entity import SesamEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SesamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button."""
    async_add_entities([OpenButton(entry.runtime_data, "open")])


class OpenButton(SesamEntity, ButtonEntity):
    """Switches the filter off and, after the configured time, back on."""

    async def async_press(self) -> None:
        """Open."""
        await self.coordinator.async_open()
