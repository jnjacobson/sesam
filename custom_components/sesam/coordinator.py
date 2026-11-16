"""Polls the MAC filter and runs the timed opening."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FRITZ_ENTRY,
    CONF_MINUTES,
    DEFAULT_MINUTES,
    DOMAIN,
    LOGGER,
)
from .door import (
    BOX_ERRORS,
    Box,
    FilterNotApplied,
    FilterUnsupported,
    find_bands,
    read_filter,
    write_filter,
)

type SesamConfigEntry = ConfigEntry[SesamCoordinator]

POLL_INTERVAL = timedelta(minutes=1)
CLOSE_RETRY = timedelta(minutes=1)
STORAGE_VERSION = 1


def storage_key(entry_id: str) -> str:
    """Return the storage key that holds the pending close time."""
    return f"{DOMAIN}.{entry_id}"


class SesamCoordinator(DataUpdateCoordinator[bool]):
    """Holds whether the MAC filter is on and when an opening ends."""

    config_entry: SesamConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SesamConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass, LOGGER, config_entry=entry, name=DOMAIN, update_interval=POLL_INTERVAL
        )
        self.closes_at: datetime | None = None
        self._bands: list[str] = []
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._cancel_close: CALLBACK_TYPE | None = None
        self._write_lock = asyncio.Lock()

    def _box(self) -> Box:
        # Looked up on every use: reloading the fritz integration replaces it.
        entry = self.hass.config_entries.async_get_entry(
            self.config_entry.data[CONF_FRITZ_ENTRY]
        )
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="fritz_not_loaded"
            )
        return Box(entry.runtime_data.connection)

    async def _async_setup(self) -> None:
        try:
            self._bands = await self.hass.async_add_executor_job(
                find_bands, self._box()
            )
        except (HomeAssistantError, *BOX_ERRORS) as err:
            raise UpdateFailed(str(err)) from err
        if not self._bands:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="unsupported"
            )
        # An opening that was running when Home Assistant stopped still has to end.
        stored = await self._store.async_load()
        if stored and (closes_at := dt_util.parse_datetime(stored["closes_at"])):
            self._schedule_close(closes_at)

    async def _async_update_data(self) -> bool:
        try:
            return await self.hass.async_add_executor_job(
                read_filter, self._box(), self._bands
            )
        except (HomeAssistantError, *BOX_ERRORS) as err:
            raise UpdateFailed(str(err)) from err

    async def async_qr_code(self) -> bytes:
        """Return a PNG of the QR code that lets a phone join the home Wi-Fi."""
        # The bands of one home network share name and password; any one will do.
        return await self.hass.async_add_executor_job(
            self._box().qr_code, self._bands[0]
        )

    async def async_open(self, minutes: int | None = None) -> None:
        """Switch the filter off now and back on after the given minutes."""
        if minutes is None:
            minutes = self.config_entry.options.get(CONF_MINUTES, DEFAULT_MINUTES)
        closes_at = dt_util.utcnow() + timedelta(minutes=minutes)
        # Saved and scheduled before opening, and kept if opening fails: a write
        # that only got through on one band is then still undone.
        await self._store.async_save({"closes_at": closes_at.isoformat()})
        self._schedule_close(closes_at)
        await self._async_write(False)

    async def async_set_filter(self, enabled: bool) -> None:
        """Switch the filter for good, dropping any running opening."""
        await self._async_forget_close()
        await self._async_write(enabled)

    async def _async_write(self, enabled: bool) -> None:
        async with self._write_lock:
            box = self._box()
            try:
                await self.hass.async_add_executor_job(
                    write_filter, box, self._bands, enabled
                )
            except FilterUnsupported as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_write",
                    translation_placeholders={"error": str(err)},
                ) from err
            except FilterNotApplied as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="not_applied"
                ) from err
            except BOX_ERRORS as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="box_error",
                    translation_placeholders={"error": str(err)},
                ) from err
        self.async_set_updated_data(enabled)

    @callback
    def _schedule_close(self, when: datetime) -> None:
        self.async_cancel_close()
        self.closes_at = when
        # A time in the past fires right away.
        self._cancel_close = async_track_point_in_utc_time(
            self.hass, self._async_close_due, when
        )
        self.async_update_listeners()

    async def _async_close_due(self, _now: datetime) -> None:
        self._cancel_close = None
        try:
            await self._async_write(True)
        except HomeAssistantError as err:
            LOGGER.error(
                "Could not switch the MAC filter back on, trying again in a minute: %s",
                err,
            )
            self._cancel_close = async_track_point_in_utc_time(
                self.hass, self._async_close_due, dt_util.utcnow() + CLOSE_RETRY
            )
            return
        await self._async_forget_close()

    async def _async_forget_close(self) -> None:
        self.async_cancel_close()
        self.closes_at = None
        await self._store.async_remove()
        self.async_update_listeners()

    @callback
    def async_cancel_close(self) -> None:
        """Stop the timer; the stored close time survives for the next start."""
        if self._cancel_close:
            self._cancel_close()
            self._cancel_close = None
