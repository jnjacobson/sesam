"""The MAC filter as a switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SesamConfigEntry
from .entity import SesamEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SesamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch."""
    async_add_entities([MacFilterSwitch(entry.runtime_data, "mac_filter")])


class MacFilterSwitch(SesamEntity, SwitchEntity):
    """On while only known devices may join the Wi-Fi."""

    @property
    def is_on(self) -> bool:
        """Return whether the filter is on."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return when a running opening ends."""
        closes_at = self.coordinator.closes_at
        return {"closes_at": closes_at.isoformat() if closes_at else None}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the filter on."""
        await self.coordinator.async_set_filter(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the filter off until it is switched on again."""
        await self.coordinator.async_set_filter(False)
