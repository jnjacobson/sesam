"""The QR code that lets a phone join the home Wi-Fi."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import LOGGER
from .coordinator import SesamConfigEntry, SesamCoordinator
from .door import BOX_ERRORS
from .entity import SesamEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SesamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the QR code."""
    async_add_entities([QrCodeImage(hass, entry.runtime_data, "qr_code")])


class QrCodeImage(SesamEntity, ImageEntity):
    """Asks the box for name and password each time the picture is fetched."""

    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, coordinator: SesamCoordinator, key: str
    ) -> None:
        """Initialize."""
        SesamEntity.__init__(self, coordinator, key)
        ImageEntity.__init__(self, hass)
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        """Return the QR code as PNG."""
        try:
            return await self.coordinator.async_qr_code()
        except (HomeAssistantError, *BOX_ERRORS) as err:
            LOGGER.warning("Could not get the Wi-Fi QR code from the box: %s", err)
            return None
